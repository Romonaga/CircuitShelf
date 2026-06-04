"""Table and direct-pattern pinout extractors."""

from __future__ import annotations

import re

from backend.ingestion.pinout_model import (
    PIN_TABLE_PAGE_MARKERS,
    PinoutPin,
    clean_pin_label,
    compact_header,
    expand_pin_label,
)
from backend.ingestion.pinout_signals import clean_signal_label, is_signal_label


DIRECT_PIN_PATTERN = re.compile(
    r"\bpin\s*(?P<pin>\d{1,2})\s*[:=\-–]\s*(?P<name>[A-Za-z][A-Za-z0-9 +/_-]{1,40})",
    re.IGNORECASE,
)


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


def extract_pipe_table_pinout(
    text: str,
    *,
    source: str,
    page: int | None,
    chunk_index: int | None,
) -> list[PinoutPin]:
    rows = [_split_table_row(line) for line in str(text or "").splitlines() if "|" in line]
    rows = [row for row in rows if row]
    if len(rows) < 2:
        return []

    header_index = next((index for index, row in enumerate(rows) if _looks_like_pin_table_header(row)), -1)
    if header_index < 0:
        return []
    header = [compact_header(cell) for cell in rows[header_index]]
    pin_col = _first_header_index(header, {"PIN", "PIN#", "PINNO", "PINNUMBER", "NO", "NUMBER", "TERMINAL"})
    if pin_col is None:
        return []
    name_col = _first_header_index(header, {"NAME", "SYMBOL", "SIGNAL", "TERMINALNAME", "MNEMONIC"})
    function_col = _first_header_index(header, {"FUNCTION", "DESCRIPTION", "TYPE", "I/O", "IO"})

    pins = []
    for row in rows[header_index + 1 :]:
        if pin_col >= len(row):
            continue
        pin_number = _pin_number_from_cell(row[pin_col])
        if pin_number is None:
            continue
        label = _label_from_table_columns(row, name_col=name_col, function_col=function_col, pin_col=pin_col)
        if not is_signal_label(label):
            continue
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


def extract_compact_optocoupler_pinout(
    text: str,
    *,
    source: str,
    page: int | None,
    chunk_index: int | None,
) -> list[PinoutPin]:
    """Handle common PDF-extracted optocoupler diagram text."""

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


def _looks_like_pin_description_table(lines: list[str]) -> bool:
    upper_lines = [line.upper() for line in lines]
    joined = "\n".join(upper_lines)
    has_marker = any(marker in joined for marker in PIN_TABLE_PAGE_MARKERS)
    has_pin_header = any(line in {"PIN #", "PIN", "PIN NUMBER", "NO.", "NO"} for line in upper_lines)
    return has_marker and has_pin_header


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


def _split_table_row(line: str) -> list[str]:
    cells = [clean_pin_label(cell) for cell in str(line or "").split("|")]
    return [cell for cell in cells if cell]


def _looks_like_pin_table_header(row: list[str]) -> bool:
    compact = {compact_header(cell) for cell in row}
    has_pin = bool(compact & {"PIN", "PIN#", "PINNO", "PINNUMBER", "NO", "NUMBER", "TERMINAL"})
    has_label = bool(compact & {"NAME", "SYMBOL", "SIGNAL", "FUNCTION", "DESCRIPTION", "TERMINALNAME", "MNEMONIC"})
    return has_pin and has_label


def _first_header_index(header: list[str], names: set[str]) -> int | None:
    for index, value in enumerate(header):
        if value in names:
            return index
    return None


def _pin_number_from_cell(value: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\b", str(value or ""))
    if not match:
        return None
    pin = int(match.group(1))
    return pin if 1 <= pin <= 256 else None


def _label_from_table_columns(row: list[str], *, name_col: int | None, function_col: int | None, pin_col: int) -> str:
    candidates: list[str] = []
    if name_col is not None and name_col < len(row):
        candidates.append(row[name_col])
    if function_col is not None and function_col < len(row):
        candidates.append(row[function_col])
    candidates.extend(cell for index, cell in enumerate(row) if index != pin_col)

    for candidate in candidates:
        cleaned = clean_signal_label(candidate)
        if is_signal_label(cleaned):
            return cleaned
    return ""
