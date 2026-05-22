"""Deterministic pinout extraction helpers for datasheet text."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


DIRECT_PIN_PATTERN = re.compile(
    r"\bpin\s*(?P<pin>\d{1,2})\s*[:=\-–]\s*(?P<name>[A-Za-z][A-Za-z0-9 +/_-]{1,40})",
    re.IGNORECASE,
)


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

    for index, text in enumerate(chunks):
        meta = metadata[index] if index < len(metadata) else {}
        candidate_source = meta.get("parent_source") or meta.get("source") or source
        if candidate_source != source:
            continue
        page = _optional_int(meta.get("page"))
        candidates = []
        candidates.extend(extract_compact_optocoupler_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_pin_description_table_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_direct_pinouts(text, source=source, page=page, chunk_index=index))
        for pin in candidates:
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
