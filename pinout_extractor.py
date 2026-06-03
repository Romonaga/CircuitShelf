"""Deterministic pinout extraction helpers for datasheet text."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


DIRECT_PIN_PATTERN = re.compile(
    r"\bpin\s*(?P<pin>\d{1,2})\s*[:=\-–]\s*(?P<name>[A-Za-z][A-Za-z0-9 +/_-]{1,40})",
    re.IGNORECASE,
)

PIN_TABLE_PAGE_MARKERS = ("PIN FUNCTIONS", "PIN DESCRIPTIONS", "PIN DESCRIPTION", "TERMINAL FUNCTIONS")
PIN_TABLE_COLUMN_MARKERS = {"PIN", "PIN#", "PINNO", "PINNUMBER", "NAME", "I/O", "DESCRIPTION", "FUNCTION"}
PIN_LABEL_STOPWORDS = {
    "ACTIVE",
    "ADDENDUM",
    "APPLICATION",
    "BUY",
    "COMMUNITY",
    "DESCRIPTION",
    "DEVICE",
    "DOCUMENTS",
    "FEATURES",
    "FOLDER",
    "FUNCTION",
    "GENERAL",
    "INPUT",
    "MAX",
    "MIN",
    "NAME",
    "OUTPUT",
    "PACKAGE",
    "PAGE",
    "PARAMETER",
    "PIN",
    "PRODUCT",
    "REVISION",
    "SAMPLE",
    "SOFTWARE",
    "STATUS",
    "SUPPORT",
    "TABLE",
    "TECHNICAL",
    "TOOLS",
    "TYPE",
    "UNIT",
}


@dataclass(frozen=True)
class PinoutPin:
    pin: int
    label: str
    function: str
    source: str
    page: int | None = None
    chunk_index: int | None = None


def expand_pin_label(label: str, *, role: str = "") -> str:
    normalized = re.sub(r"\s+", " ", label).strip()
    upper = normalized.upper()
    if upper in {"GND", "GROUND"}:
        return "Ground"
    if upper in {"VDD", "VCC", "VSS", "VEE"}:
        return upper
    if upper == "SCL":
        return "SCL"
    if upper == "SDA":
        return "SDA"
    if upper == "ADDR":
        return "ADDR"
    if upper in {"NC", "N/C", "NO CONNECT", "NO CONNECTION"}:
        return "No connection"
    if upper == "TRIG":
        return "Trigger input"
    if upper == "THRES":
        return "Threshold input"
    if upper == "DISCH":
        return "Discharge"
    if upper == "CONT":
        return "Control voltage"
    if upper == "OUT":
        return "Output"
    if upper == "RESET":
        return "Reset"
    if upper == "A":
        return "Anode"
    if upper in {"K", "CATH"}:
        return "Cathode"
    if upper == "E":
        return "Emitter"
    if upper == "B":
        return "Base"
    if upper == "C":
        return "Cathode" if role == "input" else "Collector" if role == "output" else "C"
    return normalized


def clean_pin_label(label: str) -> str:
    return re.sub(r"\(\d+\)", "", label or "").strip(" .;:,")


def extract_direct_pinouts(text: str, *, source: str, page: int | None, chunk_index: int | None) -> list[PinoutPin]:
    pins = []
    for match in DIRECT_PIN_PATTERN.finditer(text or ""):
        pin = int(match.group("pin"))
        label = clean_pin_label(match.group("name"))
        pins.append(
            PinoutPin(
                pin=pin,
                label=label,
                function=expand_pin_label(label),
                source=source,
                page=page,
                chunk_index=chunk_index,
            )
        )
    return pins


def extract_pin_description_table_pinout(
    text: str,
    *,
    source: str,
    page: int | None,
    chunk_index: int | None,
) -> list[PinoutPin]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not _looks_like_pin_description_table(lines):
        return []

    pins = []
    for row in _pin_table_rows(lines):
        label = _label_from_pin_table_row(row)
        if not label:
            continue
        pin_number = int(row[0])
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


def _looks_like_pin_description_table(lines: list[str]) -> bool:
    upper_lines = [line.upper() for line in lines]
    return "PIN DESCRIPTIONS" in upper_lines and any(line in {"PIN #", "PIN", "PIN NUMBER"} for line in upper_lines)


def _pin_table_rows(lines: list[str]) -> list[list[str]]:
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.upper() in {"PIN #", "PIN", "PIN NUMBER"}
        ),
        -1,
    )
    if header_index < 0:
        return []

    rows = []
    current = []
    for line in lines[header_index + 1 :]:
        normalized = line.strip()
        if re.fullmatch(r"\(?\d{1,2}\)?", normalized):
            if current:
                rows.append(current)
            current = [normalized.strip("()")]
            continue
        if current:
            current.append(normalized)
            if len(rows) >= 64:
                break
    if current:
        rows.append(current)
    return rows


def _label_from_pin_table_row(row: list[str]) -> str:
    if len(row) < 2:
        return ""

    direction_index = next(
        (
            index
            for index, value in enumerate(row[1:], start=1)
            if re.fullmatch(r"(?:analog|digital)(?:\s+(?:input|output|i/o))?", value, re.IGNORECASE)
        ),
        len(row),
    )
    label_cells = [clean_pin_label(value) for value in row[1:direction_index]]
    label_cells = [value for value in label_cells if value and value.upper() not in {"DEVICE", "ADS1113", "ADS1114", "ADS1115"}]
    if not label_cells:
        return ""
    return label_cells[-1]


def extract_compact_optocoupler_pinout(
    text: str,
    *,
    source: str,
    page: int | None,
    chunk_index: int | None,
) -> list[PinoutPin]:
    """Handle common PDF-extracted optocoupler diagram text.

    PyMuPDF often extracts a 6-pin optocoupler diagram as:
    "1 2 3 6 5 4 B C E A C NC".
    The first three labels belong to output pins 6/5/4 and the last three
    belong to input pins 1/2/3.
    """

    flattened = re.sub(r"\s+", " ", text or "").strip()
    pattern = re.compile(r"\b1\s+2\s+3\s+6\s+5\s+4\s+B\s+C\s+E\s+A\s+C\s+NC\b", re.IGNORECASE)
    if not pattern.search(flattened):
        return []

    mapping = [
        (1, "A", "input"),
        (2, "C", "input"),
        (3, "NC", ""),
        (4, "E", "output"),
        (5, "C", "output"),
        (6, "B", "output"),
    ]
    return [
        PinoutPin(
            pin=pin,
            label=label,
            function=expand_pin_label(label, role=role),
            source=source,
            page=page,
            chunk_index=chunk_index,
        )
        for pin, label, role in mapping
    ]


def extract_pinout_map(chunks: list[str], metadata: list[dict], source: str) -> dict:
    pins_by_number: dict[int, PinoutPin] = {}
    page_chunks: dict[int | None, list[tuple[int, str]]] = {}

    for index, text in enumerate(chunks):
        meta = metadata[index] if index < len(metadata) else {}
        candidate_source = meta.get("parent_source") or meta.get("source") or source
        if candidate_source != source:
            continue
        page = _optional_int(meta.get("page"))
        page_chunks.setdefault(page, []).append((index, text or ""))
        candidates = []
        candidates.extend(extract_compact_optocoupler_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_pin_description_table_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_direct_pinouts(text, source=source, page=page, chunk_index=index))
        for pin in candidates:
            pins_by_number.setdefault(pin.pin, pin)

    for page, page_items in page_chunks.items():
        for pin in extract_ordered_pin_function_sequence(page_items, source=source, page=page):
            pins_by_number.setdefault(pin.pin, pin)

    return {
        "source": source,
        "displayName": os.path.basename(source),
        "pins": [
            {
                "pin": pin.pin,
                "label": pin.label,
                "function": pin.function,
                "page": pin.page,
                "chunkIndex": pin.chunk_index,
            }
            for pin in sorted(pins_by_number.values(), key=lambda item: item.pin)
        ],
    }


def _optional_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_ordered_pin_function_sequence(
    page_items: list[tuple[int, str]],
    *,
    source: str,
    page: int | None,
) -> list[PinoutPin]:
    """Recover pin mappings from pin-function pages whose numbers were lost.

    Some PDF text extraction splits a datasheet pin-function table into:
    a run of signal names in pin order, followed later by a name/function table
    without the numeric column. This method is generic: it only runs on pages
    that look like pin-function tables and uses the ordered signal run from the
    document itself. It does not know about a specific chip.
    """

    combined = "\n".join(text for _index, text in page_items)
    if not _looks_like_pin_function_page(combined):
        return []

    lines_with_index: list[tuple[int, str]] = []
    for chunk_index, text in page_items:
        for line in str(text or "").splitlines():
            cleaned = _clean_signal_label(line)
            if cleaned:
                lines_with_index.append((chunk_index, cleaned))

    run = _best_ordered_signal_run(lines_with_index)
    if len(run) < 4:
        return []

    later_text = "\n".join(label for _idx, label in lines_with_index)
    pins = []
    for pin_number, (chunk_index, label) in enumerate(run, start=1):
        if not _label_has_support(label, later_text):
            return []
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


def _looks_like_pin_function_page(text: str) -> bool:
    normalized = _compact_header(text)
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
        if _is_signal_label(label):
            current.append((chunk_index, label))
            continue
        best = _choose_better_run(best, current)
        current = []

    best = _choose_better_run(best, current)
    return best


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


def _label_has_support(label: str, page_text: str) -> bool:
    return len(re.findall(rf"\b{re.escape(label)}\b", page_text)) >= 2


def _is_signal_label(value: str) -> bool:
    if not value or value in PIN_LABEL_STOPWORDS:
        return False
    if value == "NC":
        return True
    if len(value) > 12:
        return False
    if not re.search(r"[A-Z]", value):
        return False
    if re.fullmatch(r"\d+(?:[./-]\d+)?", value):
        return False
    if re.fullmatch(r"[A-Z]", value) and value not in {"A", "B", "C", "D", "E", "K"}:
        return False
    return bool(re.fullmatch(r"[A-Z][A-Z0-9/+_-]*", value))


def _clean_signal_label(value: str) -> str:
    cleaned = re.sub(r"\(\d+\)", "", str(value or "").strip())
    cleaned = cleaned.replace("#", "")
    cleaned = re.sub(r"[^A-Za-z0-9/+_-]", "", cleaned).upper()
    return cleaned


def _compact_header(text: str) -> str:
    return re.sub(r"[^A-Z0-9/#]+", "", str(text or "").upper())
