"""Recover ordered pin mappings from pin-function pages."""

from __future__ import annotations

import re

from backend.ingestion.pinout_model import (
    PIN_TABLE_COLUMN_MARKERS,
    PIN_TABLE_PAGE_MARKERS,
    PinoutPin,
    compact_header,
    expand_pin_label,
)
from backend.ingestion.pinout_signals import is_signal_label, label_has_support, signal_lines_with_index


def extract_ordered_pin_function_sequence(
    page_items: list[tuple[int, str]],
    *,
    source: str,
    page: int | None,
) -> list[PinoutPin]:
    """Recover pin mappings from pin-function pages whose numbers were lost."""

    combined = "\n".join(text for _index, text in page_items)
    if not _looks_like_pin_function_page(combined):
        return []

    diagram_items = _page_items_before_pin_table_marker(page_items)
    if not diagram_items:
        return []
    lines_with_index = signal_lines_with_index(diagram_items)

    run = _best_ordered_signal_run(lines_with_index)
    if len(run) < 4:
        return []

    support_text = _pin_support_text(combined)
    if not support_text:
        return []
    run = _trim_to_plausible_pin_sequence(
        [(chunk_index, label) for chunk_index, label in run if label_has_support(label, support_text)]
    )
    if len(run) < 4:
        return []

    pins = []
    for pin_number, (chunk_index, label) in enumerate(run, start=1):
        pins.append(
            PinoutPin(
                pin=pin_number,
                label=label,
                function=expand_pin_label(label),
                source=source,
                page=page,
                chunk_index=chunk_index,
            )
        )
    return pins


def _page_items_before_pin_table_marker(page_items: list[tuple[int, str]]) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for chunk_index, text in page_items:
        raw = str(text or "")
        marker_positions = [raw.upper().find(marker) for marker in PIN_TABLE_PAGE_MARKERS if raw.upper().find(marker) >= 0]
        if marker_positions:
            before_marker = raw[: min(marker_positions)]
            if before_marker.strip():
                result.append((chunk_index, before_marker))
            break
        result.append((chunk_index, raw))
    return result


def _looks_like_pin_function_page(text: str) -> bool:
    normalized = compact_header(text)
    has_page_marker = any(marker.replace(" ", "") in normalized for marker in PIN_TABLE_PAGE_MARKERS)
    if not has_page_marker:
        return False
    column_hits = sum(1 for marker in PIN_TABLE_COLUMN_MARKERS if marker in normalized)
    return column_hits >= 3


def _best_ordered_signal_run(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    best: list[tuple[int, str]] = []
    current: list[tuple[int, str]] = []

    for chunk_index, label in lines:
        if label == "NC" and len(current) >= 4:
            best = _choose_better_run(best, current)
            current = []
            continue
        if is_signal_label(label):
            current.append((chunk_index, label))
            continue
        best = _choose_better_run(best, current)
        current = []

    best = _choose_better_run(best, current)
    return best


def _trim_to_plausible_pin_sequence(run: list[tuple[int, str]]) -> list[tuple[int, str]]:
    if len(run) < 4:
        return []
    common_counts = (4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 64)
    if len(run) in common_counts:
        return run

    candidates = [run[:count] for count in common_counts if 4 <= count <= len(run)]
    if not candidates:
        return run
    return max(candidates, key=_pin_sequence_score)


def _pin_sequence_score(run: list[tuple[int, str]]) -> int:
    labels = [label for _idx, label in run]
    score = 0
    score += sum(4 for label in labels if label in {"GND", "VCC", "+VCC", "VDD", "VSS", "VEE", "V+"})
    score += sum(2 for label in labels if label in {"OUT", "OUTPUT", "RESET", "SCL", "SDA", "TRIG", "TRIGGER", "THRES", "THRESHOLD"})
    score += sum(1 for label in labels if label not in {"NC", "N/C"})
    score -= sum(3 for label in labels if label in {"NC", "N/C"})
    return score


def _choose_better_run(best: list[tuple[int, str]], current: list[tuple[int, str]]) -> list[tuple[int, str]]:
    deduped = _dedupe_preserve_order(current)
    if 4 <= len(deduped) <= 32 and _signal_run_score(deduped) > _signal_run_score(best):
        return deduped
    return best


def _signal_run_score(run: list[tuple[int, str]]) -> int:
    if not run:
        return 0
    labels = [label for _idx, label in run]
    score = len(labels)
    score += sum(1 for label in labels if label in {"GND", "VCC", "VDD", "VSS", "OUT", "RESET", "SCL", "SDA"})
    score -= sum(1 for label in labels if re.fullmatch(r"[A-Z]", label))
    return score


def _dedupe_preserve_order(run: list[tuple[int, str]]) -> list[tuple[int, str]]:
    seen = set()
    result = []
    for item in run:
        if item[1] in seen:
            continue
        seen.add(item[1])
        result.append(item)
    return result


def _pin_support_text(text: str) -> str:
    upper = str(text or "").upper()
    marker_positions = [upper.find(marker) for marker in PIN_TABLE_PAGE_MARKERS if upper.find(marker) >= 0]
    if not marker_positions:
        return ""
    return upper[min(marker_positions) :]
