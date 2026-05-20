#!/usr/bin/env python3
"""Audit persisted RAG chunks for size, metadata, and source distribution."""

from __future__ import annotations

import argparse
import json
import pickle
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_pickle(path: Path) -> Any:
    with path.open("rb") as handle:
        return pickle.load(handle)


def approx_tokens(text: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def compact(text: str, limit: int = 180) -> str:
    snippet = " ".join(str(text).split())
    if len(snippet) > limit:
        return snippet[: limit - 3] + "..."
    return snippet


def build_report(data_dir: Path, sample_limit: int) -> dict[str, Any]:
    chunks = load_pickle(data_dir / "chunks.pkl")
    sources = load_pickle(data_dir / "sources.pkl")
    metadata = load_pickle(data_dir / "metadata.pkl")

    rows = []
    source_summary: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "tokens": [], "pages": Counter()})
    section_counts = Counter()
    missing_page = 0
    missing_section = 0

    for index, chunk in enumerate(chunks):
        source = sources[index] if index < len(sources) else ""
        meta = metadata[index] if index < len(metadata) and isinstance(metadata[index], dict) else {}
        tokens = approx_tokens(str(chunk))
        page = meta.get("page")
        section = meta.get("section") or meta.get("section_header") or ""

        if page in (None, "", 0):
            missing_page += 1
        if not section:
            missing_section += 1

        summary = source_summary[source]
        summary["count"] += 1
        summary["tokens"].append(tokens)
        if page not in (None, ""):
            summary["pages"][str(page)] += 1
        section_counts[section or "<missing>"] += 1

        rows.append(
            {
                "index": index,
                "source": source,
                "page": page,
                "section": section,
                "tokens": tokens,
                "chars": len(str(chunk)),
                "snippet": compact(str(chunk)),
            }
        )

    token_lengths = [row["tokens"] for row in rows]
    short_rows = sorted(rows, key=lambda row: row["tokens"])[:sample_limit]
    long_rows = sorted(rows, key=lambda row: row["tokens"], reverse=True)[:sample_limit]

    source_rows = []
    for source, summary in source_summary.items():
        tokens = summary["tokens"]
        source_rows.append(
            {
                "source": source,
                "count": summary["count"],
                "avg_tokens": round(statistics.fmean(tokens), 1) if tokens else 0.0,
                "min_tokens": min(tokens) if tokens else 0,
                "max_tokens": max(tokens) if tokens else 0,
                "page_count": len(summary["pages"]),
            }
        )
    source_rows.sort(key=lambda row: (-row["count"], row["source"]))

    return {
        "data_dir": str(data_dir),
        "chunk_count": len(chunks),
        "source_count": len(source_summary),
        "metadata_count": len(metadata),
        "avg_tokens": round(statistics.fmean(token_lengths), 1) if token_lengths else 0.0,
        "median_tokens": round(statistics.median(token_lengths), 1) if token_lengths else 0.0,
        "min_tokens": min(token_lengths) if token_lengths else 0,
        "max_tokens": max(token_lengths) if token_lengths else 0,
        "missing_page": missing_page,
        "missing_section": missing_section,
        "top_sections": section_counts.most_common(15),
        "top_sources": source_rows[:25],
        "short_samples": short_rows,
        "long_samples": long_rows,
    }


def print_markdown(report: dict[str, Any]) -> None:
    print("# Chunk Audit")
    print()
    print(f"- Data dir: {report['data_dir']}")
    print(f"- Chunks: {report['chunk_count']}")
    print(f"- Sources: {report['source_count']}")
    print(f"- Metadata rows: {report['metadata_count']}")
    print(f"- Avg tokens: {report['avg_tokens']}")
    print(f"- Median tokens: {report['median_tokens']}")
    print(f"- Token range: {report['min_tokens']} to {report['max_tokens']}")
    print(f"- Missing page metadata: {report['missing_page']}")
    print(f"- Missing section metadata: {report['missing_section']}")
    print()

    print("## Top Sources")
    for row in report["top_sources"]:
        print(
            f"- {row['source']}: {row['count']} chunks, avg={row['avg_tokens']}, "
            f"range={row['min_tokens']}-{row['max_tokens']}, pages={row['page_count']}"
        )
    print()

    print("## Top Sections")
    for section, count in report["top_sections"]:
        print(f"- {section}: {count}")
    print()

    print("## Short Samples")
    for row in report["short_samples"]:
        print(f"- #{row['index']} {row['source']} page={row['page']} tokens={row['tokens']}: {row['snippet']}")
    print()

    print("## Long Samples")
    for row in report["long_samples"]:
        print(f"- #{row['index']} {row['source']} page={row['page']} tokens={row['tokens']}: {row['snippet']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit persisted RAG chunks.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--json", type=Path, help="Optional path to write the full report as JSON.")
    args = parser.parse_args()

    report = build_report(args.data_dir, args.samples)
    print_markdown(report)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
