"""Deterministic pinout extraction helpers for datasheet text."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


DIRECT_PIN_PATTERN = re.compile(
    r"\bpin\s*(?P<pin>\d{1,2})\s*[:=\-–]\s*(?P<name>[A-Za-z][A-Za-z0-9 +/_-]{1,40})",
    re.IGNORECASE,
)

PIN_TABLE_PAGE_MARKERS = (
    "PIN FUNCTIONS",
    "PIN DESCRIPTIONS",
    "PIN DESCRIPTION",
    "PIN CONFIGURATION",
    "PIN CONFIGURATIONS",
    "FUNCTIONAL PINOUT",
    "CONNECTION DIAGRAM",
    "TERMINAL FUNCTIONS",
    "TERMINAL ASSIGNMENTS",
    "PIN ASSIGNMENTS",
)
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
    if upper in {"+VCC", "V+", "VCC+"}:
        return "VCC"
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
    if upper in {"TRIG", "TRIGGER"}:
        return "Trigger input"
    if upper in {"THRES", "THRESHOLD"}:
        return "Threshold input"
    if upper in {"DISCH", "DISCHARGE"}:
        return "Discharge"
    if upper in {"CONT", "CONTROL", "CONTROL VOLTAGE"}:
        return "Control voltage"
    if upper in {"OUT", "OUTPUT"}:
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
        ordered_pins = extract_ordered_pin_function_sequence(page_items, source=source, page=page)
        if _should_replace_existing_pinout(ordered_pins, pins_by_number):
            for pin in ordered_pins:
                pins_by_number[pin.pin] = pin
        else:
            for pin in ordered_pins:
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


def _should_replace_existing_pinout(ordered_pins: list[PinoutPin], existing: dict[int, PinoutPin]) -> bool:
    if len(ordered_pins) < 4:
        return False
    if len(ordered_pins) > len(existing):
        return True
    ordered_score = _pinout_evidence_score(ordered_pins)
    existing_score = _pinout_evidence_score(list(existing.values()))
    return ordered_score > existing_score


def _pinout_evidence_score(pins: list[PinoutPin]) -> int:
    labels = [pin.label.upper() for pin in pins]
    score = len(pins) * 2
    score += sum(3 for label in labels if label in {"GND", "VCC", "VDD", "VSS", "VEE", "V+"})
    score += sum(1 for label in labels if label not in {"NC", "N/C"})
    score -= sum(2 for label in labels if label in {"NC", "N/C"})
    return score


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

    diagram_items = _page_items_before_pin_table_marker(page_items)
    if not diagram_items:
        return []
    lines_with_index = _signal_lines_with_index(diagram_items)

    run = _best_ordered_signal_run(lines_with_index)
    if len(run) < 4:
        return []

    support_text = _pin_support_text(combined)
    if not support_text:
        return []
    run = _trim_to_plausible_pin_sequence(
        [(chunk_index, label) for chunk_index, label in run if _label_has_support(label, support_text)]
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


def _signal_lines_with_index(page_items: list[tuple[int, str]]) -> list[tuple[int, str]]:
    raw: list[tuple[int, str]] = []
    for chunk_index, text in page_items:
        for line in str(text or "").splitlines():
            raw.append((chunk_index, line))

    result: list[tuple[int, str]] = []
    index = 0
    while index < len(raw):
        chunk_index, line = raw[index]
        cleaned = _clean_signal_label(line)
        next_cleaned = _clean_signal_label(raw[index + 1][1]) if index + 1 < len(raw) else ""
        if cleaned == "CONTROL" and next_cleaned == "VOLTAGE":
            result.append((chunk_index, "CONTROL VOLTAGE"))
            index += 2
            continue
        if cleaned:
            result.append((chunk_index, cleaned))
        index += 1
    return result


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


def _label_has_support(label: str, page_text: str) -> bool:
    support_labels = {support_label for _idx, support_label in _signal_lines_with_index([(0, page_text)])}
    support_compact = _compact_header(page_text)
    for alias in _label_support_aliases(label):
        if alias in support_labels:
            return True
        if len(alias) >= 2 and alias in support_compact:
            return True
    return False


def _label_support_aliases(label: str) -> set[str]:
    compact = _compact_header(label)
    aliases = {compact}
    if compact in {"VCC", "V"}:
        aliases.update({"VCC", "V+"})
    if compact in {"TRIG", "TRIGGER"}:
        aliases.update({"TRIG", "TRIGGER"})
    if compact in {"THRES", "THRESHOLD"}:
        aliases.update({"THRES", "THRESHOLD"})
    if compact in {"DISCH", "DISCHARGE"}:
        aliases.update({"DISCH", "DISCHARGE"})
    if compact in {"CONT", "CONTROL", "CONTROLVOLTAGE"}:
        aliases.update({"CONT", "CONTROL", "CONTROLVOLTAGE"})
    if compact in {"OUT", "OUTPUT"}:
        aliases.update({"OUT", "OUTPUT"})
    return aliases


def _is_signal_label(value: str) -> bool:
    if not value or value in PIN_LABEL_STOPWORDS:
        if value != "OUTPUT":
            return False
    if value == "CONTROL VOLTAGE":
        return True
    compact = _compact_header(value)
    if "TOPVIEW" in compact or "PACKAGE" in compact or re.search(r"\bPIN\b", value):
        return False
    if value == "NC":
        return True
    if len(value) > 16:
        return False
    if " " in value:
        return False
    if not re.search(r"[A-Z]", value):
        return False
    if re.fullmatch(r"\d+(?:[./-]\d+)?", value):
        return False
    if re.fullmatch(r"[A-Z]", value) and value not in {"A", "B", "C", "D", "E", "K"}:
        return False
    return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9/+_-]*", value))


def _clean_signal_label(value: str) -> str:
    cleaned = re.sub(r"\(\d+\)", "", str(value or "").strip())
    cleaned = cleaned.replace("#", "")
    cleaned = re.sub(r"[^A-Za-z0-9/+_ -]", "", cleaned).upper()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned in {"+VCC", "VCC+", "VCC"}:
        return "VCC"
    return cleaned


def _compact_header(text: str) -> str:
    return re.sub(r"[^A-Z0-9/#]+", "", str(text or "").upper())


def _pin_support_text(text: str) -> str:
    upper = str(text or "").upper()
    marker_positions = [upper.find(marker) for marker in PIN_TABLE_PAGE_MARKERS if upper.find(marker) >= 0]
    if not marker_positions:
        return ""
    return upper[min(marker_positions) :]
