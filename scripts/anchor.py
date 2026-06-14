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

Storage: docs/traces/anchors.csv (same dir / style as the other Yoke indexes).

Schema (anchors.csv):
  anchor_id, doc_kind, doc_ref, code_file, span, symbol, content_hash, status, added

  anchor_id    stable id: A-{8hex} hash of doc_ref + code_file + span
  doc_kind     learning | component | trace | map   (what kind of doc)
  doc_ref      pointer into the doc store, e.g. a learning `key`, or a path
  code_file    path to the source file (repo-relative)
  span         "L42-L67"  line range, or "FULL" for whole file
  symbol       optional human label of what's anchored (e.g. "AuthMiddleware.handle")
  content_hash sha256[:16] of the code span's normalized text
  status       fresh | stale | missing
  added        YYYY-MM-DD

Usage:
  python3 anchor.py add --doc-kind learning --doc-ref date-field-utc \\
      --code-file src/models/user.py --span L10-L40 --symbol "User.created_at"
  python3 anchor.py scan                 # recompute hashes, mark stale/missing
  python3 anchor.py list [--status stale]
  python3 anchor.py verify --anchor-id A-1a2b3c4d   # mark one anchor fresh again
  python3 anchor.py report               # human-readable staleness report (for agents)

Pure stdlib. No tree-sitter required (line-range anchoring works for any
language); a symbol resolver can be layered on later without changing the schema.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from datetime import date
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

SPAN_RE = re.compile(r"^L(\d+)-L(\d+)$")


# ============================================================================
# Hashing
# ============================================================================

def normalize_code(text):
    """
    Normalize a code span before hashing so that cosmetic-only changes
    (trailing whitespace, blank-line padding, CRLF) don't trigger false stale.
    Indentation and content are preserved — those are meaningful.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [ln.rstrip() for ln in lines]
    # drop leading / trailing blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def hash_span(project_dir, code_file, span):
    """
    Return (content_hash, status). status is 'missing' if the file or the
    requested line range can't be read.
    """
    path = Path(project_dir) / code_file
    if not path.exists() or not path.is_file():
        return "", "missing"

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", "missing"

    if span == "FULL":
        snippet = raw
    else:
        m = SPAN_RE.match(span)
        if not m:
            return "", "missing"
        lo, hi = int(m.group(1)), int(m.group(2))
        all_lines = raw.split("\n")
        if lo < 1 or lo > len(all_lines):
            return "", "missing"
        # clamp hi to file length (file may have shrunk); still hashable
        hi = min(hi, len(all_lines))
        snippet = "\n".join(all_lines[lo - 1:hi])

    digest = hashlib.sha256(normalize_code(snippet).encode("utf-8")).hexdigest()[:16]
    return digest, "fresh"


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

    span = args.span or "FULL"
    if span != "FULL" and not SPAN_RE.match(span):
        return {"error": f"Invalid span: {span}. Use 'FULL' or 'L<start>-L<end>' (e.g. L10-L40)."}

    content_hash, status = hash_span(project_dir, args.code_file, span)
    if status == "missing":
        return {"error": f"Cannot read {args.code_file} span {span} — file or range missing."}

    anchor_id = make_anchor_id(args.doc_ref, args.code_file, span)
    rows = load_anchors(traces_dir)

    # upsert by anchor_id
    existing = next((r for r in rows if r.get("anchor_id") == anchor_id), None)
    record = {
        "anchor_id": anchor_id,
        "doc_kind": args.doc_kind,
        "doc_ref": args.doc_ref,
        "code_file": args.code_file,
        "span": span,
        "symbol": args.symbol or "",
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
    return {"action": action, "anchor": record}


def cmd_scan(project_dir, traces_dir, args):
    """Recompute every anchor's hash. Flip status to fresh/stale/missing."""
    rows = load_anchors(traces_dir)
    changed = []
    counts = {"fresh": 0, "stale": 0, "missing": 0}

    for r in rows:
        new_hash, status = hash_span(project_dir, r["code_file"], r["span"])
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
                "anchor_id": r["anchor_id"],
                "doc_kind": r["doc_kind"],
                "doc_ref": r["doc_ref"],
                "code_file": r["code_file"],
                "span": r["span"],
                "from": prev_status,
                "to": new_status,
            })
        r["status"] = new_status
        # NOTE: we keep the original content_hash so the anchor still remembers
        # what it was validated against. `verify` re-baselines it.

    save_anchors(traces_dir, rows)
    return {"scanned": len(rows), "counts": counts, "changed": changed}


def cmd_verify(project_dir, traces_dir, args):
    """Re-baseline one anchor to current code (mark fresh again)."""
    rows = load_anchors(traces_dir)
    target = next((r for r in rows if r.get("anchor_id") == args.anchor_id), None)
    if not target:
        return {"error": f"No anchor with id {args.anchor_id}"}
    new_hash, status = hash_span(project_dir, target["code_file"], target["span"])
    if status == "missing":
        return {"error": f"Cannot re-baseline — {target['code_file']} span {target['span']} missing."}
    target["content_hash"] = new_hash
    target["status"] = "fresh"
    save_anchors(traces_dir, rows)
    return {"verified": target["anchor_id"], "content_hash": new_hash}


def cmd_list(project_dir, traces_dir, args):
    rows = load_anchors(traces_dir)
    if args.status:
        rows = [r for r in rows if r.get("status") == args.status]
    if args.doc_kind:
        rows = [r for r in rows if r.get("doc_kind") == args.doc_kind]
    return {"count": len(rows), "anchors": rows}


def cmd_report(project_dir, traces_dir, args):
    """Human/agent-readable staleness report. Scans first for live accuracy."""
    scan = cmd_scan(project_dir, traces_dir, args)
    rows = load_anchors(traces_dir)
    stale = [r for r in rows if r.get("status") == "stale"]
    missing = [r for r in rows if r.get("status") == "missing"]
    return {
        "summary": scan["counts"],
        "stale": stale,
        "missing": missing,
        "total": len(rows),
    }


# ============================================================================
# Output formatting
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
        out.append("Action: re-read the code, then update the doc and run "
                   "`anchor.py verify --anchor-id <id>` to re-baseline.")
        out.append("")

    if result["missing"]:
        out.append("### ❌ Missing — the anchored file/range no longer exists")
        out.append("")
        out.append("| anchor | doc | code | span |")
        out.append("|---|---|---|---|")
        for r in result["missing"]:
            out.append(f"| {r['anchor_id']} | {r['doc_kind']}:{r['doc_ref']} "
                       f"| {r['code_file']} | {r['span']} |")
        out.append("")
        out.append("Action: the code moved or was deleted. Re-anchor the doc or retire it.")
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
    p_add.add_argument("--span", default="FULL", help="'FULL' or 'L<start>-L<end>' (default: FULL)")
    p_add.add_argument("--symbol", default="", help="Optional label, e.g. 'AuthMiddleware.handle'")

    sub.add_parser("scan", help="Recompute hashes, flip stale/missing/fresh")

    p_list = sub.add_parser("list", help="List anchors")
    p_list.add_argument("--status", choices=list(VALID_STATUSES))
    p_list.add_argument("--doc-kind", choices=list(VALID_DOC_KINDS))

    p_ver = sub.add_parser("verify", help="Re-baseline one anchor to current code")
    p_ver.add_argument("--anchor-id", required=True)

    sub.add_parser("report", help="Staleness report for humans/agents")

    args = parser.parse_args()
    traces_dir = Path(args.project_dir) / "docs" / "traces"

    dispatch = {
        "add": cmd_add,
        "scan": cmd_scan,
        "list": cmd_list,
        "verify": cmd_verify,
        "report": cmd_report,
    }
    result = dispatch[args.command](args.project_dir, traces_dir, args)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "report":
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
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        a = result["anchor"]
        print(f"{result['action']}: {a['anchor_id']}  "
              f"{a['doc_kind']}:{a['doc_ref']} -> {a['code_file']} {a['span']}  "
              f"[{a['content_hash']}]")
    elif args.command == "verify":
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"verified {result['verified']} — re-baselined to {result['content_hash']}")
    elif args.command == "list":
        print(f"{result['count']} anchor(s)")
        for r in result["anchors"]:
            print(f"  {r['anchor_id']}  [{r['status']}]  "
                  f"{r['doc_kind']}:{r['doc_ref']} -> {r['code_file']} {r['span']}  "
                  f"{r.get('symbol','')}")


if __name__ == "__main__":
    main()
