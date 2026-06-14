#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yoke Artifact Search — BM25 search engine for development artifacts.

Searches CSV indexes in a project's docs/traces/ directory.
Replaces generate-map.ts for MAP.md generation.

Usage:
  python3 search.py "<query>" [--domain <domain>] [--module <mod>] [--status <s>]
  python3 search.py --generate-map [--config <path>]
  python3 search.py --init

Domains: index (default), files, tests, apis, tech_debt
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import defaultdict
from math import log
from pathlib import Path

# Force UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


# ============================================================================
# Constants
# ============================================================================

CSV_TABLES = {
    "index": {
        "file": "index.csv",
        "search_cols": ["id", "title", "keywords", "module", "component"],
        "output_cols": [
            "id", "type", "phase", "module", "component", "title",
            "keywords", "status", "author", "date", "file",
            "depends_on", "depended_by",
        ],
        "headers": [
            "id", "type", "phase", "module", "component", "title",
            "keywords", "status", "author", "date", "file",
            "depends_on", "depended_by",
        ],
    },
    "files": {
        "file": "files.csv",
        "search_cols": ["feat_id", "path", "desc"],
        "output_cols": ["feat_id", "path", "desc", "lines"],
        "headers": ["feat_id", "path", "desc", "lines"],
    },
    "tests": {
        "file": "tests.csv",
        "search_cols": ["feat_id", "path"],
        "output_cols": ["feat_id", "path", "count"],
        "headers": ["feat_id", "path", "count"],
    },
    "apis": {
        "file": "apis.csv",
        "search_cols": ["feat_id", "method", "path", "desc"],
        "output_cols": ["feat_id", "method", "path", "desc"],
        "headers": ["feat_id", "method", "path", "desc"],
    },
    "tech_debt": {
        "file": "tech_debt.csv",
        "search_cols": ["feat_id", "td_id", "desc"],
        "output_cols": ["feat_id", "td_id", "priority", "desc", "added", "resolved_by"],
        "headers": ["feat_id", "td_id", "priority", "desc", "added", "resolved_by"],
    },
}

VALID_TYPES = ("FEAT", "BUG", "REFACTOR", "PATCH")
VALID_PHASES = ("trace", "spec", "audit", "stuck")
VALID_STATUSES = ("draft", "confirmed", "in-progress", "done", "pass", "fail", "rejected")


# ============================================================================
# BM25 Implementation (adapted from ui-ux-pro-max)
# ============================================================================

class BM25:
    """BM25 ranking algorithm for text search."""

    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus = []
        self.doc_lengths = []
        self.avgdl = 0
        self.idf = {}
        self.doc_freqs = defaultdict(int)
        self.N = 0

    def tokenize(self, text):
        text = re.sub(r"[^\w\s]", " ", str(text).lower())
        return [w for w in text.split() if len(w) > 1]

    def fit(self, documents):
        self.corpus = [self.tokenize(doc) for doc in documents]
        self.N = len(self.corpus)
        if self.N == 0:
            return
        self.doc_lengths = [len(doc) for doc in self.corpus]
        self.avgdl = sum(self.doc_lengths) / self.N

        for doc in self.corpus:
            seen = set()
            for word in doc:
                if word not in seen:
                    self.doc_freqs[word] += 1
                    seen.add(word)

        for word, freq in self.doc_freqs.items():
            self.idf[word] = log((self.N - freq + 0.5) / (freq + 0.5) + 1)

    def score(self, query):
        query_tokens = self.tokenize(query)
        scores = []
        for idx, doc in enumerate(self.corpus):
            s = 0
            doc_len = self.doc_lengths[idx]
            term_freqs = defaultdict(int)
            for word in doc:
                term_freqs[word] += 1
            for token in query_tokens:
                if token in self.idf:
                    tf = term_freqs[token]
                    idf = self.idf[token]
                    num = tf * (self.k1 + 1)
                    den = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                    s += idf * num / den
            scores.append((idx, s))
        return sorted(scores, key=lambda x: x[1], reverse=True)


# ============================================================================
# CSV Operations
# ============================================================================

def load_csv(filepath):
    """Load CSV, return list of dicts. Returns [] if file missing."""
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_csv(filepath, row, headers):
    """Append a row to CSV. Creates file with headers if missing."""
    exists = filepath.exists() and filepath.stat().st_size > 0
    with open(filepath, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def init_csv(traces_dir):
    """Initialize empty CSV files with headers in docs/traces/."""
    traces_dir = Path(traces_dir)
    traces_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for table_name, config in CSV_TABLES.items():
        filepath = traces_dir / config["file"]
        if not filepath.exists():
            with open(filepath, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(config["headers"])
            created.append(config["file"])
    return created


# ============================================================================
# FEAT-ID Generation
# ============================================================================

def generate_feat_id(feat_type, title, date_str=None):
    """
    Generate a FEAT-ID: {TYPE}-{4hex}-{slug}

    Hash is computed from date + title for idempotency.
    Slug is 2-3 words extracted from title, kebab-case.
    """
    feat_type = feat_type.upper()
    if feat_type not in VALID_TYPES:
        raise ValueError(f"Invalid type: {feat_type}. Must be one of {VALID_TYPES}")

    # Hash: SHA256 of date+title, take first 4 hex chars
    hash_input = f"{date_str or ''}{title}".encode("utf-8")
    short_hash = hashlib.sha256(hash_input).hexdigest()[:4]

    # Slug: extract keywords, kebab-case, max 3 words
    slug = re.sub(r"[^\w\s]", "", title.lower())
    # Remove common stop words
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "in", "on", "at", "to", "for", "of", "with", "and", "or",
                  "not", "no", "but", "if", "do", "does", "did", "will",
                  "would", "could", "should", "may", "might", "can",
                  "this", "that", "these", "those", "it", "its"}
    words = [w for w in slug.split() if w and w not in stop_words]
    slug = "-".join(words[:3])

    if not slug:
        slug = short_hash

    return f"{feat_type}-{short_hash}-{slug}"


# ============================================================================
# Search Functions
# ============================================================================

def search(traces_dir, query, domain="index", max_results=5, filters=None):
    """
    BM25 search across a CSV table.

    Args:
        traces_dir: Path to docs/traces/
        query: Search query string
        domain: CSV table to search (index, files, tests, apis, tech_debt)
        max_results: Max results to return
        filters: Dict of column->value filters applied post-search
    """
    filters = filters or {}
    config = CSV_TABLES.get(domain)
    if not config:
        return {"error": f"Unknown domain: {domain}. Available: {', '.join(CSV_TABLES.keys())}"}

    filepath = Path(traces_dir) / config["file"]
    data = load_csv(filepath)
    if not data:
        return {"domain": domain, "query": query, "count": 0, "results": []}

    # Apply pre-filters
    if filters:
        filtered_data = []
        for row in data:
            match = True
            for col, val in filters.items():
                if col in row and row[col].lower() != val.lower():
                    match = False
                    break
            if match:
                filtered_data.append(row)
        data = filtered_data

    if not data:
        return {"domain": domain, "query": query, "count": 0, "results": [], "filters": filters}

    # BM25 search (or return all if no query)
    if query:
        documents = [
            " ".join(str(row.get(col, "")) for col in config["search_cols"])
            for row in data
        ]
        bm25 = BM25()
        bm25.fit(documents)
        ranked = bm25.score(query)

        results = []
        for idx, score in ranked[:max_results]:
            if score > 0:
                row = data[idx]
                results.append({col: row.get(col, "") for col in config["output_cols"] if col in row})
    else:
        # No query, return filtered results (up to max)
        results = [
            {col: row.get(col, "") for col in config["output_cols"] if col in row}
            for row in data[:max_results]
        ]

    return {
        "domain": domain,
        "query": query or "(all)",
        "count": len(results),
        "results": results,
        "filters": filters if filters else None,
    }


# ============================================================================
# MAP.md Generation
# ============================================================================

def generate_map(traces_dir, config_path=None):
    """
    Generate MAP.md content from CSV data.
    Replaces generate-map.ts.

    Args:
        traces_dir: Path to docs/traces/
        config_path: Optional path to yoke.map.config.json
    """
    traces_dir = Path(traces_dir)
    index_data = load_csv(traces_dir / "index.csv")
    files_data = load_csv(traces_dir / "files.csv")
    tests_data = load_csv(traces_dir / "tests.csv")
    apis_data = load_csv(traces_dir / "apis.csv")
    td_data = load_csv(traces_dir / "tech_debt.csv")

    # Load config if available
    labels = {}
    domains = {}
    if config_path:
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                domains = config.get("domains", {})
                labels = config.get("labels", {})

    map_title = labels.get("mapTitle", "MAP — Knowledge Graph")
    feat_index_title = labels.get("featureIndex", "Feature Index")
    td_title = labels.get("techDebt", "Tech Debt")

    # Group index entries by unique FEAT-ID (trace phase only for main index)
    trace_entries = [r for r in index_data if r.get("phase") == "trace"]

    # Build lookup tables
    files_by_feat = defaultdict(list)
    for r in files_data:
        files_by_feat[r["feat_id"]].append(r)

    tests_by_feat = defaultdict(list)
    for r in tests_data:
        tests_by_feat[r["feat_id"]].append(r)

    apis_by_feat = defaultdict(list)
    for r in apis_data:
        apis_by_feat[r["feat_id"]].append(r)

    # Build MAP.md
    lines = [f"# {map_title}", ""]

    # Feature index table
    lines.append(f"## {feat_index_title}")
    lines.append("")
    col_id = labels.get("columns", {}).get("id", "ID")
    col_title = labels.get("columns", {}).get("title", "Title")
    col_domain = labels.get("columns", {}).get("domain", "Module")
    col_status = labels.get("columns", {}).get("status", "Status")
    col_tests = labels.get("columns", {}).get("testCount", "Tests")
    col_files = labels.get("columns", {}).get("fileCount", "Files")

    lines.append(f"| {col_id} | {col_title} | {col_domain} | {col_status} | {col_files} | {col_tests} |")
    lines.append("|---|---|---|---|---|---|")

    for entry in trace_entries:
        feat_id = entry.get("id", "")
        title = entry.get("title", "")
        module = entry.get("module", "")
        status = entry.get("status", "")
        file_count = len(files_by_feat.get(feat_id, []))
        test_count = sum(int(t.get("count", 0)) for t in tests_by_feat.get(feat_id, []))
        lines.append(f"| {feat_id} | {title} | {module} | {status} | {file_count} | {test_count} |")

    lines.append("")

    # API summary
    if apis_data:
        lines.append("## APIs")
        lines.append("")
        lines.append("| FEAT | Method | Path | Desc |")
        lines.append("|---|---|---|---|")
        for r in apis_data:
            lines.append(f"| {r.get('feat_id','')} | {r.get('method','')} | {r.get('path','')} | {r.get('desc','')} |")
        lines.append("")

    # Tech debt
    unresolved_td = [r for r in td_data if not r.get("resolved_by")]
    if unresolved_td:
        lines.append(f"## {td_title}")
        lines.append("")
        lines.append("| ID | FEAT | Priority | Desc | Added |")
        lines.append("|---|---|---|---|---|")
        for r in unresolved_td:
            lines.append(
                f"| {r.get('td_id','')} | {r.get('feat_id','')} | {r.get('priority','')} "
                f"| {r.get('desc','')} | {r.get('added','')} |"
            )
        lines.append("")

    # Domain sub-maps (if config available)
    if domains and trace_entries:
        lines.append("## Domain Sub-Maps")
        lines.append("")
        by_domain = defaultdict(list)
        for entry in trace_entries:
            by_domain[entry.get("module", "unknown")].append(entry)
        for domain_slug, label in domains.items():
            entries = by_domain.get(domain_slug, [])
            if entries:
                lines.append(f"### {label} ({domain_slug})")
                lines.append("")
                for e in entries:
                    lines.append(f"- **{e['id']}**: {e.get('title','')} [{e.get('status','')}]")
                lines.append("")

    return "\n".join(lines)


# ============================================================================
# Output Formatting
# ============================================================================

def format_output(result):
    """Format search results for terminal display."""
    if "error" in result:
        return f"Error: {result['error']}"

    output = [f"## Yoke Artifact Search"]
    output.append(f"**Domain:** {result['domain']} | **Query:** {result['query']}")
    if result.get("filters"):
        output.append(f"**Filters:** {result['filters']}")
    output.append(f"**Found:** {result['count']} results\n")

    for i, row in enumerate(result["results"], 1):
        output.append(f"### Result {i}")
        for key, value in row.items():
            value_str = str(value)
            if len(value_str) > 300:
                value_str = value_str[:300] + "..."
            output.append(f"- **{key}:** {value_str}")
        output.append("")

    return "\n".join(output)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Yoke Artifact Search")
    parser.add_argument("query", nargs="?", default="", help="Search query")
    parser.add_argument("--domain", "-d", choices=list(CSV_TABLES.keys()),
                        default="index", help="CSV table to search")
    parser.add_argument("--max-results", "-n", type=int, default=5, help="Max results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Filters
    parser.add_argument("--module", "-m", type=str, help="Filter by module")
    parser.add_argument("--status", "-s", type=str, help="Filter by status")
    parser.add_argument("--type", "-t", type=str, help="Filter by type (FEAT/BUG/...)")
    parser.add_argument("--phase", type=str, help="Filter by phase (trace/spec/audit)")
    parser.add_argument("--priority", type=str, help="Filter by priority (tech_debt domain)")

    # MAP.md generation
    parser.add_argument("--generate-map", action="store_true", help="Generate MAP.md content")
    parser.add_argument("--config", type=str, help="Path to yoke.map.config.json")

    # Init
    parser.add_argument("--init", action="store_true", help="Initialize empty CSV files")

    # Project dir
    parser.add_argument("--project-dir", "-p", type=str, default=".",
                        help="Project root directory (default: current dir)")

    # FEAT-ID generation
    parser.add_argument("--generate-id", action="store_true",
                        help="Generate a FEAT-ID from --type and --title")
    parser.add_argument("--title", type=str, help="Title for FEAT-ID generation")
    parser.add_argument("--date", type=str, help="Date for FEAT-ID generation (YYYY-MM-DD)")

    args = parser.parse_args()
    traces_dir = Path(args.project_dir) / "docs" / "traces"

    # Init mode
    if args.init:
        created = init_csv(traces_dir)
        if created:
            print(f"Initialized CSV files in {traces_dir}: {', '.join(created)}")
        else:
            print(f"All CSV files already exist in {traces_dir}")
        sys.exit(0)

    # FEAT-ID generation mode
    if args.generate_id:
        if not args.type or not args.title:
            print("Error: --generate-id requires --type and --title", file=sys.stderr)
            sys.exit(1)
        feat_id = generate_feat_id(args.type, args.title, args.date)
        if args.json:
            print(json.dumps({"id": feat_id}, ensure_ascii=False))
        else:
            print(feat_id)
        sys.exit(0)

    # MAP.md generation mode
    if args.generate_map:
        content = generate_map(traces_dir, args.config)
        print(content)
        sys.exit(0)

    # Search mode
    filters = {}
    if args.module:
        filters["module"] = args.module
    if args.status:
        filters["status"] = args.status
    if args.type:
        filters["type"] = args.type
    if args.phase:
        filters["phase"] = args.phase
    if args.priority:
        filters["priority"] = args.priority

    result = search(traces_dir, args.query, args.domain, args.max_results, filters)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_output(result))
