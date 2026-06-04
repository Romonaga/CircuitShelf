"""Pinout candidate scoring and replacement rules."""

from __future__ import annotations

from backend.ingestion.pinout_model import PinoutPin


def should_replace_existing_pinout(ordered_pins: list[PinoutPin], existing: dict[int, PinoutPin]) -> bool:
    if len(ordered_pins) < 4:
        return False
    if len(ordered_pins) > len(existing):
        return True
    ordered_score = pinout_evidence_score(ordered_pins)
    existing_score = pinout_evidence_score(list(existing.values()))
    return ordered_score > existing_score


def pinout_evidence_score(pins: list[PinoutPin]) -> int:
    labels = [pin.label.upper() for pin in pins]
    score = len(pins) * 2
    score += sum(3 for label in labels if label in {"GND", "VCC", "VDD", "VSS", "VEE", "V+"})
    score += sum(1 for label in labels if label not in {"NC", "N/C"})
    score -= sum(2 for label in labels if label in {"NC", "N/C"})
    return score
