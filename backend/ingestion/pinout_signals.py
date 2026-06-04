"""Signal-label filtering helpers used by deterministic pinout extraction."""

from __future__ import annotations

import re

from backend.ingestion.pinout_model import PIN_LABEL_STOPWORDS, compact_header


def is_signal_label(value: str) -> bool:
    if not value or value in PIN_LABEL_STOPWORDS:
        if value != "OUTPUT":
            return False
    if value == "CONTROL VOLTAGE":
        return True
    compact = compact_header(value)
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


def clean_signal_label(value: str) -> str:
    cleaned = re.sub(r"\(\d+\)", "", str(value or "").strip())
    cleaned = cleaned.replace("#", "")
    cleaned = re.sub(r"[^A-Za-z0-9/+_ -]", "", cleaned).upper()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned in {"+VCC", "VCC+", "VCC"}:
        return "VCC"
    return cleaned


def signal_lines_with_index(page_items: list[tuple[int, str]]) -> list[tuple[int, str]]:
    raw: list[tuple[int, str]] = []
    for chunk_index, text in page_items:
        for line in str(text or "").splitlines():
            raw.append((chunk_index, line))

    result: list[tuple[int, str]] = []
    index = 0
    while index < len(raw):
        chunk_index, line = raw[index]
        cleaned = clean_signal_label(line)
        next_cleaned = clean_signal_label(raw[index + 1][1]) if index + 1 < len(raw) else ""
        if cleaned == "CONTROL" and next_cleaned == "VOLTAGE":
            result.append((chunk_index, "CONTROL VOLTAGE"))
            index += 2
            continue
        if cleaned:
            result.append((chunk_index, cleaned))
        index += 1
    return result


def label_has_support(label: str, page_text: str) -> bool:
    support_labels = {support_label for _idx, support_label in signal_lines_with_index([(0, page_text)])}
    support_compact = compact_header(page_text)
    for alias in label_support_aliases(label):
        if alias in support_labels:
            return True
        if len(alias) >= 2 and alias in support_compact:
            return True
    return False


def label_support_aliases(label: str) -> set[str]:
    compact = compact_header(label)
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
