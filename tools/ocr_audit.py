#!/usr/bin/env python3
"""Audit OCR text quality without importing the full RAG application.

The indexer is expensive and noisy, so this script gives a quick view of what
OCR text was accepted into the image text store. It can read either the
persisted pickle file or the extracted ``.txt`` sidecar files.
"""

from __future__ import annotations

import argparse
import json
import pickle
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = Path("config/config.yaml")
DEFAULT_IMAGE_TEXT = Path("data/image_page_text.pkl")
DEFAULT_EXTRACTED_DIR = Path("extracted_images")


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_ocr_texts(image_text_file: Path, extracted_dir: Path) -> dict[str, str]:
    if image_text_file.exists():
        with image_text_file.open("rb") as handle:
            data = pickle.load(handle)
        return {str(key): str(value) for key, value in data.items()}

    if not extracted_dir.exists():
        return {}

    texts: dict[str, str] = {}
    for path in sorted(extracted_dir.glob("*.txt")):
        try:
            texts[path.stem] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return texts


def evaluate_ocr_quality(text: str, config: dict[str, Any]) -> tuple[float, str, dict[str, float]]:
    text = text.strip()
    if not text:
        return 0.0, "Empty", {
            "length": 0,
            "unique_chars": 0,
            "avg_word_len": 0.0,
            "alpha_ratio": 0.0,
            "digit_ratio": 0.0,
            "space_ratio": 0.0,
            "symbol_ratio": 0.0,
        }

    words = text.split()
    metrics = {
        "length": float(len(text)),
        "unique_chars": float(len(set(text))),
        "avg_word_len": statistics.fmean(len(word) for word in words) if words else 0.0,
        "alpha_ratio": sum(char.isalpha() for char in text) / len(text),
        "digit_ratio": sum(char.isdigit() for char in text) / len(text),
        "space_ratio": sum(char.isspace() for char in text) / len(text),
        "symbol_ratio": sum(not char.isalnum() and not char.isspace() for char in text) / len(text),
    }

    min_length = config.get("OCR_MIN_LENGTH", 20)
    min_unique_chars = config.get("OCR_MIN_UNIQUE_CHARS", 10)
    max_avg_word_len = config.get("OCR_MAX_AVG_WORD_LEN", 12)
    min_alpha_ratio = config.get("OCR_MIN_ALPHA_RATIO", 0.3)
    max_symbol_ratio = config.get("OCR_MAX_SYMBOL_RATIO", 0.4)
    max_digit_ratio = config.get("OCR_MAX_DIGIT_RATIO", 0.5)
    max_space_ratio = config.get("OCR_MAX_SPACE_RATIO", 0.3)

    score = 1.0
    details: list[str] = []

    if len(text) < min_length:
        score -= 0.4
        details.append("too short")
    if metrics["unique_chars"] < min_unique_chars:
        score -= 0.3
        details.append("low uniqueness")
    if metrics["avg_word_len"] > max_avg_word_len:
        score -= 0.2
        details.append("long words")
    if metrics["alpha_ratio"] < min_alpha_ratio:
        score -= 0.2
        details.append("low alphabetic ratio")
    if metrics["symbol_ratio"] > max_symbol_ratio:
        score -= 0.2
        details.append("too many symbols")
    if metrics["digit_ratio"] > max_digit_ratio:
        score -= 0.2
        details.append("too many digits")
    if metrics["space_ratio"] > max_space_ratio:
        score -= 0.2
        details.append("too much whitespace")
    if re.fullmatch(r"[^a-zA-Z0-9]+", text):
        score = 0.0
        details.append("non-alphanumeric only")

    return max(0.0, round(score, 2)), ", ".join(details) or "ok", metrics


def source_name(item_id: str) -> str:
    return item_id.split("_page", 1)[0]


def compact_snippet(text: str, limit: int = 160) -> str:
    snippet = " ".join(text.split())
    if len(snippet) > limit:
        return snippet[: limit - 3] + "..."
    return snippet


def bucket(score: float) -> str:
    if score < 0.2:
        return "0.00-0.19"
    if score < 0.4:
        return "0.20-0.39"
    if score < 0.6:
        return "0.40-0.59"
    if score < 0.8:
        return "0.60-0.79"
    return "0.80-1.00"


def build_report(
    texts: dict[str, str],
    config: dict[str, Any],
    sample_limit: int,
    drop_score_override: float | None = None,
) -> dict[str, Any]:
    drop_score = float(drop_score_override if drop_score_override is not None else config.get("OCR_TXT_DROP_SCORE", 0.4))
    rows = []
    reasons = Counter()
    score_buckets = Counter()
    per_source: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "chars": 0, "scores": []})

    for item_id, text in texts.items():
        score, reason, metrics = evaluate_ocr_quality(text, config)
        row = {
            "id": item_id,
            "source": source_name(item_id),
            "score": score,
            "reason": reason,
            "length": int(metrics["length"]),
            "would_drop": score < drop_score,
            "snippet": compact_snippet(text),
        }
        rows.append(row)
        score_buckets[bucket(score)] += 1
        for part in [part.strip() for part in reason.split(",") if part.strip()]:
            reasons[part] += 1
        source = per_source[row["source"]]
        source["count"] += 1
        source["chars"] += row["length"]
        source["scores"].append(score)

    rows.sort(key=lambda row: (row["score"], row["length"]))
    source_rows = []
    for name, data in per_source.items():
        scores = data["scores"]
        source_rows.append(
            {
                "source": name,
                "count": data["count"],
                "chars": data["chars"],
                "avg_score": round(statistics.fmean(scores), 3) if scores else 0.0,
                "low_score_count": sum(score < drop_score for score in scores),
            }
        )
    source_rows.sort(key=lambda row: (-row["low_score_count"], -row["count"], row["source"]))

    scores = [row["score"] for row in rows]
    lengths = [row["length"] for row in rows]
    threshold_sweep = {}
    for threshold in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
        threshold_sweep[f"{threshold:.1f}"] = sum(row["score"] < threshold for row in rows)

    return {
        "total_items": len(rows),
        "drop_score": drop_score,
        "would_drop_count": sum(row["would_drop"] for row in rows),
        "avg_score": round(statistics.fmean(scores), 3) if scores else 0.0,
        "median_score": round(statistics.median(scores), 3) if scores else 0.0,
        "avg_chars": round(statistics.fmean(lengths), 1) if lengths else 0.0,
        "score_buckets": dict(score_buckets),
        "threshold_sweep": threshold_sweep,
        "top_reasons": reasons.most_common(12),
        "worst_samples": rows[:sample_limit],
        "source_summary": source_rows[:25],
    }


def print_markdown(report: dict[str, Any]) -> None:
    print("# OCR Audit")
    print()
    print(f"- Items: {report['total_items']}")
    print(f"- Configured drop score: {report['drop_score']}")
    print(f"- Would drop at current threshold: {report['would_drop_count']}")
    print(f"- Average score: {report['avg_score']}")
    print(f"- Median score: {report['median_score']}")
    print(f"- Average chars: {report['avg_chars']}")
    print()

    print("## Score Buckets")
    for name in ["0.00-0.19", "0.20-0.39", "0.40-0.59", "0.60-0.79", "0.80-1.00"]:
        print(f"- {name}: {report['score_buckets'].get(name, 0)}")
    print()

    print("## Threshold Sweep")
    for threshold, count in report["threshold_sweep"].items():
        print(f"- Drop below {threshold}: {count}")
    print()

    print("## Top Reasons")
    for reason, count in report["top_reasons"]:
        print(f"- {reason}: {count}")
    print()

    print("## Sources With Most Low-Score OCR")
    for row in report["source_summary"]:
        print(
            f"- {row['source']}: {row['count']} items, "
            f"{row['low_score_count']} below threshold, avg={row['avg_score']}"
        )
    print()

    print("## Worst Samples")
    for row in report["worst_samples"]:
        print(f"- {row['id']} | score={row['score']} | chars={row['length']} | {row['reason']}")
        if row["snippet"]:
            print(f"  {row['snippet']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit OCR text quality for the RAG image index.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--image-text", type=Path, default=DEFAULT_IMAGE_TEXT)
    parser.add_argument("--extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--drop-score", type=float, help="Override OCR_TXT_DROP_SCORE for this audit only.")
    parser.add_argument("--json", type=Path, help="Optional path to write the full report as JSON.")
    args = parser.parse_args()

    config = load_config(args.config)
    texts = load_ocr_texts(args.image_text, args.extracted_dir)
    report = build_report(texts, config, args.samples, args.drop_score)
    print_markdown(report)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
