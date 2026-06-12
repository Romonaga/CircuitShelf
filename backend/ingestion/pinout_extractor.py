"""Public coordinator for deterministic pinout extraction."""

from __future__ import annotations

import os

from backend.ingestion.pinout_model import PinoutPin, clean_pin_label, expand_pin_label, optional_int
from backend.ingestion.pinout_scoring import should_replace_existing_pinout
from backend.ingestion.pinout_sequence import extract_ordered_pin_function_sequence
from backend.ingestion.pinout_tables import (
    extract_compact_optocoupler_pinout,
    extract_direct_pinouts,
    extract_flat_numbered_signal_table_pinout,
    extract_signal_only_pinout,
    extract_side_by_side_package_pinout,
    extract_pin_description_table_pinout,
    extract_pipe_table_pinout,
    extract_whitespace_table_pinout,
)

__all__ = [
    "PinoutPin",
    "clean_pin_label",
    "expand_pin_label",
    "extract_compact_optocoupler_pinout",
    "extract_direct_pinouts",
    "extract_flat_numbered_signal_table_pinout",
    "extract_signal_only_pinout",
    "extract_ordered_pin_function_sequence",
    "extract_pin_description_table_pinout",
    "extract_pinout_map",
    "extract_pipe_table_pinout",
    "extract_side_by_side_package_pinout",
    "extract_whitespace_table_pinout",
]


def extract_pinout_map(chunks: list[str], metadata: list[dict], source: str) -> dict:
    pins_by_number: dict[int, PinoutPin] = {}
    page_chunks: dict[int | None, list[tuple[int, str]]] = {}

    for index, text in enumerate(chunks):
        meta = metadata[index] if index < len(metadata) else {}
        candidate_source = meta.get("parent_source") or meta.get("source") or source
        if candidate_source != source:
            continue
        page = optional_int(meta.get("page"))
        page_chunks.setdefault(page, []).append((index, text or ""))
        candidates = []
        candidates.extend(extract_compact_optocoupler_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_side_by_side_package_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_flat_numbered_signal_table_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_signal_only_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_pipe_table_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_whitespace_table_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_pin_description_table_pinout(text, source=source, page=page, chunk_index=index))
        candidates.extend(extract_direct_pinouts(text, source=source, page=page, chunk_index=index))
        for pin in candidates:
            pins_by_number.setdefault(pin.pin, pin)

    for page, page_items in page_chunks.items():
        ordered_pins = extract_ordered_pin_function_sequence(page_items, source=source, page=page)
        if should_replace_existing_pinout(ordered_pins, pins_by_number):
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
