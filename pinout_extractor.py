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


def extract_direct_pinouts(text: str, *, source: str, page: int | None, chunk_index: int | None) -> list[PinoutPin]:
    pins = []
    for match in DIRECT_PIN_PATTERN.finditer(text or ""):
        pin = int(match.group("pin"))
        label = match.group("name").strip(" .;:,")
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
