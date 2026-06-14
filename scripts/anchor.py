#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yoke Anchor — ground living docs to real code, detect staleness automatically.

The missing link in Yoke: living docs (learnings, spec-layer component docs,
traces) describe code, but nothing machine-verifiable ties a doc to the exact
code it describes. When that code changes, the doc silently rots.

Anchor fixes this. Each anchor pins a doc to a span of code and stores a content
hash of that span. When the code changes, the hash changes, and the anchored doc
flips to `stale` — proactively, the moment the code moves, not when an agent
later happens to notice the doc no longer applies.

ANCHORING MODES (the `span` column):
  FULL              whole file
  L42-L67           fixed line range
  SYM:funcName      SYMBOL mode — re-locates the symbol on every scan, so
                    inserting lines ABOVE it no longer triggers a false stale.
                    This is the recommended mode. Pure-stdlib locator:
                    Python uses indentation, C-family uses brace balancing.

Storage: docs/traces/anchors.csv (same dir / style as the other Yoke indexes).

Schema (anchors.csv):
  anchor_id, doc_kind, doc_ref, code_file, span, symbol, content_hash, status, added

Usage:
  python3 anchor.py add --doc-kind learning --doc-ref date-field-utc \\
      --code-file src/models/user.py --symbol-name User.created_at      # SYMBOL mode
  python3 anchor.py add ... --code-file x.py --span L10-L40             # LINE mode
  python3 anchor.py scan                 # recompute hashes, mark stale/missing
  python3 anchor.py list [--status stale]
  python3 anchor.py verify --anchor-id A-1a2b3c4d
  python3 anchor.py report               # human/agent staleness report
  python3 anchor.py dashboard [--out docs/anchor-dashboard.html]  # single-file HTML

Pure stdlib. No tree-sitter. No external services.
"""

import argparse
import csv
import hashlib
import html
import io
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

# Force UTF-8 (match search.py behavior)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


# ============================================================================
# Constants
# ============================================================================

ANCHORS_FILE = "anchors.csv"
ANCHORS_HEADERS = [
    "anchor_id", "doc_kind", "doc_ref", "code_file",
    "span", "symbol", "content_hash", "status", "added",
]

VALID_DOC_KINDS = ("learning", "component", "trace", "map")
VALID_STATUSES = ("fresh", "stale", "missing")

SPAN_LINE_RE = re.compile(r"^L(\d+)-L(\d+)$")
SPAN_SYM_RE = re.compile(r"^SYM:(.+)$")

# Languages whose blocks are delimited by { } braces
BRACE_EXTS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".java", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp",
    ".rs", ".swift", ".kt", ".kts", ".scala", ".php", ".cs", ".dart",
}
# Languages whose blocks are delimited by indentation
INDENT_EXTS = {".py", ".pyi"}

# definition-ish keywords that distinguish "def foo()" from a call "foo()"
DEF_KEYWORDS = (
    "function", "func", "class", "struct", "interface", "type", "impl",
    "fn", "def", "trait", "enum", "object", "void", "static", "public",
    "private", "protected", "export", "async", "const", "let", "var", "val",
)


# ============================================================================
# Symbol location (pure stdlib, language-aware)
# ============================================================================

def _lang_of(code_file):
    suffix = Path(code_file).suffix.lower()
    if suffix in INDENT_EXTS:
        return "indent"
    if suffix in BRACE_EXTS:
        return "brace"
    return None


def _bare_name(symbol_name):
    """'User.created_at' -> 'created_at' (we locate the trailing member)."""
    return symbol_name.split(".")[-1].split("#")[-1].strip()


def _locate_indent(lines, name):
    """Python-style: find `def/class name`, end = last line more-indented than it."""
    pat = re.compile(r"^(\s*)(?:async\s+)?(?:def|class)\s+" + re.escape(name) + r"\b")
    for i, line in enumerate(lines):
        m = pat.match(line)
        if not m:
            continue
        base = len(m.group(1))
        end = i
        for j in range(i + 1, len(lines)):
            s = lines[j]
            if not s.strip() or s.lstrip().startswith("#"):
                continue
            indent = len(s) - len(s.lstrip())
            if indent <= base:
                break
            end = j
        return (i, end)
    return None


def _looks_like_def(line, name):
    """Heuristic: is this line a *definition* of `name`, not a call?"""
    stripped = line.strip()
    if stripped.endswith(";"):  # forward decl / statement, not a body
        # still could be a one-liner def, but treat braces below
        pass
    # must reference the name as an identifier
    if not re.search(r"\b" + re.escape(name) + r"\b", line):
        return False
    # a call usually looks like `name(...)` with no def keyword and ends ) or );
    has_kw = any(re.search(r"\b" + kw + r"\b", line) for kw in DEF_KEYWORDS)
    # `name(...) {`  pattern (method/func without leading kw, e.g. Go-ish/TS methods)
    sig_like = re.search(r"\b" + re.escape(name) + r"\s*\([^;]*\)\s*\{?\s*$", line)
    return bool(has_kw or sig_like)


def _locate_brace(lines, name):
    """C-family: find a definition line for `name`, then brace-balance to its end."""
    for i, line in enumerate(lines):
        if not _looks_like_def(line, name):
            continue
        depth = 0
        started = False
        for j in range(i, len(lines)):
            for ch in lines[j]:
                if ch == "{":
                    depth += 1
                    started = True
                elif ch == "}":
                    depth -= 1
            if started and depth <= 0:
                return (i, j)
        # no closing brace found — treat as a one-line/decl symbol
        if not started:
            return (i, i)
        return (i, len(lines) - 1)
    return None


def locate_symbol(code_file, lines, symbol_name):
    """
    Return (start_idx, end_idx) 0-based inclusive, or None if not found / lang
    unsupported. Tries full name then trailing member (User.foo -> foo).
    """
    lang = _lang_of(code_file)
    if lang is None:
        return None
    locator = _locate_indent if lang == "indent" else _locate_brace
    for candidate in (symbol_name, _bare_name(symbol_name)):
        if not candidate:
            continue
        hit = locator(lines, candidate)
        if hit:
            return hit
    return None


# ============================================================================
# Span resolution + hashing
# ============================================================================

def normalize_code(text):
    """
    Strip trailing whitespace + leading/trailing blank lines so cosmetic-only
    changes don't trigger false stale. Indentation & content are preserved.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [ln.rstrip() for ln in lines]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def resolve_span(project_dir, code_file, span, symbol_hint=""):
    """
    Return (snippet, resolved_label, status).
    status='missing' if file/range/symbol can't be resolved.
    resolved_label is a human note like 'L185-L214' showing where it landed.
    """
    path = Path(project_dir) / code_file
    if not path.exists() or not path.is_file():
        return "", span, "missing"
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", span, "missing"

    all_lines = raw.split("\n")

    if span == "FULL":
        return raw, "FULL", "fresh"

    m_line = SPAN_LINE_RE.match(span)
    if m_line:
        lo, hi = int(m_line.group(1)), int(m_line.group(2))
        if lo < 1 or lo > len(all_lines):
            return "", span, "missing"
        hi = min(hi, len(all_lines))
        return "\n".join(all_lines[lo - 1:hi]), f"L{lo}-L{hi}", "fresh"

    m_sym = SPAN_SYM_RE.match(span)
    if m_sym:
        name = m_sym.group(1).strip()
        hit = locate_symbol(code_file, all_lines, name)
        if hit is None:
            return "", span, "missing"
        s, e = hit
        return "\n".join(all_lines[s:e + 1]), f"L{s + 1}-L{e + 1}", "fresh"

    return "", span, "missing"


def hash_text(text):
    return hashlib.sha256(normalize_code(text).encode("utf-8")).hexdigest()[:16]


def compute(project_dir, code_file, span, symbol_hint=""):
    """Return (content_hash, resolved_label, status)."""
    snippet, label, status = resolve_span(project_dir, code_file, span, symbol_hint)
    if status == "missing":
        return "", label, "missing"
    return hash_text(snippet), label, "fresh"


def make_anchor_id(doc_ref, code_file, span):
    h = hashlib.sha256(f"{doc_ref}|{code_file}|{span}".encode("utf-8")).hexdigest()[:8]
    return f"A-{h}"


# ============================================================================
# CSV I/O
# ============================================================================

def load_anchors(traces_dir):
    fp = Path(traces_dir) / ANCHORS_FILE
    if not fp.exists():
        return []
    with open(fp, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_anchors(traces_dir, rows):
    traces_dir = Path(traces_dir)
    traces_dir.mkdir(parents=True, exist_ok=True)
    fp = traces_dir / ANCHORS_FILE
    with open(fp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANCHORS_HEADERS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in ANCHORS_HEADERS})


# ============================================================================
# Commands
# ============================================================================

def cmd_add(project_dir, traces_dir, args):
    if args.doc_kind not in VALID_DOC_KINDS:
        return {"error": f"Invalid doc-kind: {args.doc_kind}. Must be one of {VALID_DOC_KINDS}"}

    # Determine span: symbol mode wins if --symbol-name given
    if args.symbol_name:
        if _lang_of(args.code_file) is None:
            return {"error": f"Symbol mode unsupported for {args.code_file} "
                             f"(unknown language). Use --span L<a>-L<b> instead."}
        span = f"SYM:{args.symbol_name}"
        symbol_label = args.symbol or args.symbol_name
    else:
        span = args.span or "FULL"
        if span != "FULL" and not SPAN_LINE_RE.match(span):
            return {"error": f"Invalid span: {span}. Use 'FULL', 'L<a>-L<b>', "
                             f"or pass --symbol-name for symbol mode."}
        symbol_label = args.symbol or ""

    content_hash, label, status = compute(project_dir, args.code_file, span, symbol_label)
    if status == "missing":
        return {"error": f"Cannot resolve {args.code_file} span '{span}' — "
                         f"file, range, or symbol not found."}

    anchor_id = make_anchor_id(args.doc_ref, args.code_file, span)
    rows = load_anchors(traces_dir)
    existing = next((r for r in rows if r.get("anchor_id") == anchor_id), None)
    record = {
        "anchor_id": anchor_id,
        "doc_kind": args.doc_kind,
        "doc_ref": args.doc_ref,
        "code_file": args.code_file,
        "span": span,
        "symbol": symbol_label,
        "content_hash": content_hash,
        "status": "fresh",
        "added": (existing or {}).get("added") or date.today().isoformat(),
    }
    if existing:
        rows = [record if r.get("anchor_id") == anchor_id else r for r in rows]
        action = "updated"
    else:
        rows.append(record)
        action = "created"

    save_anchors(traces_dir, rows)
    return {"action": action, "anchor": record, "resolved": label}


def cmd_scan(project_dir, traces_dir, args):
    rows = load_anchors(traces_dir)
    changed = []
    counts = {"fresh": 0, "stale": 0, "missing": 0}

    for r in rows:
        new_hash, _, status = compute(project_dir, r["code_file"], r["span"], r.get("symbol", ""))
        prev_status = r.get("status")
        if status == "missing":
            new_status = "missing"
        elif new_hash == r.get("content_hash"):
            new_status = "fresh"
        else:
            new_status = "stale"

        counts[new_status] += 1
        if new_status != prev_status:
            changed.append({
                "anchor_id": r["anchor_id"], "doc_kind": r["doc_kind"],
                "doc_ref": r["doc_ref"], "code_file": r["code_file"],
                "span": r["span"], "from": prev_status, "to": new_status,
            })
        r["status"] = new_status

    save_anchors(traces_dir, rows)
    return {"scanned": len(rows), "counts": counts, "changed": changed}


def cmd_verify(project_dir, traces_dir, args):
    rows = load_anchors(traces_dir)
    target = next((r for r in rows if r.get("anchor_id") == args.anchor_id), None)
    if not target:
        return {"error": f"No anchor with id {args.anchor_id}"}
    new_hash, label, status = compute(project_dir, target["code_file"], target["span"], target.get("symbol", ""))
    if status == "missing":
        return {"error": f"Cannot re-baseline — {target['code_file']} span '{target['span']}' missing."}
    target["content_hash"] = new_hash
    target["status"] = "fresh"
    save_anchors(traces_dir, rows)
    return {"verified": target["anchor_id"], "content_hash": new_hash, "resolved": label}


def cmd_list(project_dir, traces_dir, args):
    rows = load_anchors(traces_dir)
    if args.status:
        rows = [r for r in rows if r.get("status") == args.status]
    if args.doc_kind:
        rows = [r for r in rows if r.get("doc_kind") == args.doc_kind]
    return {"count": len(rows), "anchors": rows}


def cmd_report(project_dir, traces_dir, args):
    scan = cmd_scan(project_dir, traces_dir, args)
    rows = load_anchors(traces_dir)
    return {
        "summary": scan["counts"],
        "stale": [r for r in rows if r.get("status") == "stale"],
        "missing": [r for r in rows if r.get("status") == "missing"],
        "total": len(rows),
    }


def cmd_dashboard(project_dir, traces_dir, args):
    cmd_scan(project_dir, traces_dir, args)  # live accuracy
    rows = load_anchors(traces_dir)
    out_path = Path(project_dir) / (args.out or "docs/anchor-dashboard.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_dashboard(rows), encoding="utf-8")
    counts = {"fresh": 0, "stale": 0, "missing": 0}
    for r in rows:
        counts[r.get("status", "fresh")] = counts.get(r.get("status", "fresh"), 0) + 1
    return {"out": str(out_path), "counts": counts, "total": len(rows)}


# ============================================================================
# HTML dashboard (single file, zero deps)
# ============================================================================

def render_dashboard(rows):
    total = len(rows)
    fresh = sum(1 for r in rows if r.get("status") == "fresh")
    stale = sum(1 for r in rows if r.get("status") == "stale")
    missing = sum(1 for r in rows if r.get("status") == "missing")
    health = round(100 * fresh / total) if total else 100
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    color = {"fresh": "#16a34a", "stale": "#d97706", "missing": "#dc2626"}
    badge = {"fresh": "FRESH", "stale": "STALE", "missing": "MISSING"}

    def row_html(r):
        st = r.get("status", "fresh")
        return (
            "<tr>"
            f"<td><code>{html.escape(r.get('anchor_id',''))}</code></td>"
            f"<td><span class='b' style='background:{color.get(st,'#888')}'>{badge.get(st,st)}</span></td>"
            f"<td>{html.escape(r.get('doc_kind',''))}<br><small>{html.escape(r.get('doc_ref',''))}</small></td>"
            f"<td>{html.escape(r.get('symbol','') or '—')}</td>"
            f"<td><code>{html.escape(r.get('code_file',''))}</code><br><small>{html.escape(r.get('span',''))}</small></td>"
            "</tr>"
        )

    # stale/missing first, then fresh — most actionable on top
    order = {"missing": 0, "stale": 1, "fresh": 2}
    rows_sorted = sorted(rows, key=lambda r: order.get(r.get("status"), 3))
    table_rows = "\n".join(row_html(r) for r in rows_sorted) or \
        "<tr><td colspan='5' style='text-align:center;color:#888'>No anchors yet.</td></tr>"

    hbar_color = "#16a34a" if health >= 90 else "#d97706" if health >= 60 else "#dc2626"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Yoke Anchor — Doc Freshness</title>
<style>
:root{{color-scheme:light dark}}
body{{font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
margin:0;background:#0d1117;color:#e6edf3}}
.wrap{{max-width:960px;margin:0 auto;padding:32px 20px}}
h1{{font-size:22px;margin:0 0 4px}}
.sub{{color:#8b949e;font-size:13px;margin-bottom:24px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px}}
.card .n{{font-size:30px;font-weight:700}}
.card .l{{font-size:12px;color:#8b949e;text-transform:uppercase;letter-spacing:.04em}}
.health{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px;margin-bottom:24px}}
.track{{height:12px;background:#30363d;border-radius:6px;overflow:hidden;margin-top:8px}}
.fill{{height:100%;width:{health}%;background:{hbar_color};transition:width .4s}}
table{{width:100%;border-collapse:collapse;background:#161b22;border:1px solid #30363d;border-radius:10px;overflow:hidden}}
th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid #21262d;vertical-align:top;font-size:13px}}
th{{background:#1c2129;color:#8b949e;text-transform:uppercase;font-size:11px;letter-spacing:.04em}}
code{{background:#21262d;padding:1px 5px;border-radius:4px;font-size:12px}}
small{{color:#8b949e}}
.b{{display:inline-block;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px}}
.foot{{color:#8b949e;font-size:12px;margin-top:20px;text-align:center}}
</style></head><body><div class="wrap">
<h1>Yoke Anchor — Living-Doc Freshness</h1>
<div class="sub">Each row is a doc pinned to a span of code. When the code changes, the doc flips to STALE — automatically. Generated {now}.</div>
<div class="cards">
  <div class="card"><div class="n">{total}</div><div class="l">Anchors</div></div>
  <div class="card"><div class="n" style="color:{color['fresh']}">{fresh}</div><div class="l">Fresh</div></div>
  <div class="card"><div class="n" style="color:{color['stale']}">{stale}</div><div class="l">Stale</div></div>
  <div class="card"><div class="n" style="color:{color['missing']}">{missing}</div><div class="l">Missing</div></div>
</div>
<div class="health"><b>Doc health: {health}%</b> of anchored docs are in sync with their code.
<div class="track"><div class="fill"></div></div></div>
<table><thead><tr><th>Anchor</th><th>Status</th><th>Doc</th><th>Symbol</th><th>Code</th></tr></thead>
<tbody>
{table_rows}
</tbody></table>
<div class="foot">Yoke Anchor · graph-grounded living docs · 100% local</div>
</div></body></html>"""


# ============================================================================
# Terminal formatting
# ============================================================================

def format_report(result):
    if "error" in result:
        return f"Error: {result['error']}"
    c = result["summary"]
    out = ["## Yoke Anchor — Staleness Report", ""]
    out.append(f"**Total anchors:** {result['total']}  ·  "
               f"fresh {c['fresh']} · stale {c['stale']} · missing {c['missing']}")
    out.append("")
    if not result["stale"] and not result["missing"]:
        out.append("All anchored docs are in sync with their code. Nothing to review.")
        return "\n".join(out)
    if result["stale"]:
        out.append("### ⚠️ Stale — code changed, the anchored doc may be wrong")
        out.append("")
        out.append("| anchor | doc | what it described | code | span |")
        out.append("|---|---|---|---|---|")
        for r in result["stale"]:
            out.append(f"| {r['anchor_id']} | {r['doc_kind']}:{r['doc_ref']} "
                       f"| {r.get('symbol','') or '—'} | {r['code_file']} | {r['span']} |")
        out.append("")
        out.append("Action: re-read the code, update the doc, then "
                   "`anchor.py verify --anchor-id <id>` to re-baseline.")
        out.append("")
    if result["missing"]:
        out.append("### ❌ Missing — the anchored code no longer exists")
        out.append("")
        out.append("| anchor | doc | code | span |")
        out.append("|---|---|---|---|")
        for r in result["missing"]:
            out.append(f"| {r['anchor_id']} | {r['doc_kind']}:{r['doc_ref']} "
                       f"| {r['code_file']} | {r['span']} |")
        out.append("")
        out.append("Action: code moved or was deleted. Re-anchor the doc or retire it.")
    return "\n".join(out)


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Yoke Anchor — ground docs to code, detect staleness")
    parser.add_argument("--project-dir", "-p", default=".", help="Project root (default: cwd)")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add or update an anchor")
    p_add.add_argument("--doc-kind", required=True, choices=list(VALID_DOC_KINDS))
    p_add.add_argument("--doc-ref", required=True, help="Doc pointer (learning key, doc path, FEAT-ID)")
    p_add.add_argument("--code-file", required=True, help="Source file (repo-relative)")
    p_add.add_argument("--span", default="", help="'FULL' or 'L<a>-L<b>' (line mode)")
    p_add.add_argument("--symbol-name", default="", help="Symbol to anchor (symbol mode, recommended): e.g. generate_feat_id")
    p_add.add_argument("--symbol", default="", help="Optional human label override")

    sub.add_parser("scan", help="Recompute hashes, flip stale/missing/fresh")

    p_list = sub.add_parser("list", help="List anchors")
    p_list.add_argument("--status", choices=list(VALID_STATUSES))
    p_list.add_argument("--doc-kind", choices=list(VALID_DOC_KINDS))

    p_ver = sub.add_parser("verify", help="Re-baseline one anchor to current code")
    p_ver.add_argument("--anchor-id", required=True)

    sub.add_parser("report", help="Staleness report for humans/agents")

    p_dash = sub.add_parser("dashboard", help="Write a single-file HTML freshness dashboard")
    p_dash.add_argument("--out", default="", help="Output path (default: docs/anchor-dashboard.html)")

    args = parser.parse_args()
    traces_dir = Path(args.project_dir) / "docs" / "traces"

    dispatch = {
        "add": cmd_add, "scan": cmd_scan, "list": cmd_list,
        "verify": cmd_verify, "report": cmd_report, "dashboard": cmd_dashboard,
    }
    result = dispatch[args.command](args.project_dir, traces_dir, args)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "report":
        print(format_report(result))
    elif args.command == "scan":
        c = result["counts"]
        print(f"Scanned {result['scanned']} anchors — "
              f"fresh {c['fresh']} · stale {c['stale']} · missing {c['missing']}")
        for ch in result["changed"]:
            print(f"  {ch['anchor_id']}  {ch['from']} -> {ch['to']}  "
                  f"({ch['doc_kind']}:{ch['doc_ref']} @ {ch['code_file']} {ch['span']})")
    elif args.command == "add":
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr); sys.exit(1)
        a = result["anchor"]
        print(f"{result['action']}: {a['anchor_id']}  {a['doc_kind']}:{a['doc_ref']} "
              f"-> {a['code_file']} {a['span']} (resolved {result['resolved']})  [{a['content_hash']}]")
    elif args.command == "verify":
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr); sys.exit(1)
        print(f"verified {result['verified']} — re-baselined to {result['content_hash']} ({result['resolved']})")
    elif args.command == "list":
        print(f"{result['count']} anchor(s)")
        for r in result["anchors"]:
            print(f"  {r['anchor_id']}  [{r['status']}]  {r['doc_kind']}:{r['doc_ref']} "
                  f"-> {r['code_file']} {r['span']}  {r.get('symbol','')}")
    elif args.command == "dashboard":
        c = result["counts"]
        print(f"Wrote {result['out']} — {result['total']} anchors "
              f"(fresh {c['fresh']} · stale {c['stale']} · missing {c['missing']})")


if __name__ == "__main__":
    main()
