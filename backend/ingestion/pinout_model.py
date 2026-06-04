"""Shared pinout extraction data model and label normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass


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


def compact_header(text: str) -> str:
    return re.sub(r"[^A-Z0-9/#]+", "", str(text or "").upper())


def optional_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
