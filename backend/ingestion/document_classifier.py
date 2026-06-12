from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from backend.ingestion.models import DocumentProfile, ExtractedPage


PART_PATTERNS = [
    re.compile(r"\bADS\d{3,5}[A-Z0-9-]*\b", re.IGNORECASE),
    re.compile(r"\bESP32(?:-[A-Z0-9-]+)?\b", re.IGNORECASE),
    re.compile(r"\b(?:L293D?|L298N?|L78\d{2}|L79\d{2}|ULN2003|ULN2803|A4988)\b", re.IGNORECASE),
    re.compile(r"\b(?:MCP|PCA|PCF|SSD|BMP|BME|DHT|DS|MAX|LTC|ULN|TB|CP|CH|HX|DRV)\s?-?\d[A-Z0-9-]{1,12}\b", re.IGNORECASE),
    re.compile(r"\b(?:NE|LM|TL|TLC|SN|CD|IRF|IRL|BC|2N|1N|ATMEGA|ATTINY)\s?-?\d[A-Z0-9-]{1,12}\b", re.IGNORECASE),
    re.compile(r"\b(?:74HC|74HCT|74LS|74ALS|74LVC)\s?-?\d[A-Z0-9-]{1,8}\b", re.IGNORECASE),
    re.compile(r"\b4N(?:25|26|27|28|32|33|35|36|37|38)\b", re.IGNORECASE),
    re.compile(r"\b(?:NE|LM)?55[56]\b", re.IGNORECASE),
    re.compile(r"\b(?:ATMEGA328P|RP2040|WS2812B)\b", re.IGNORECASE),
]

FILENAME_PART_PATTERN = re.compile(r"\b[A-Z]{1,8}\d[A-Z0-9]{2,18}\b", re.IGNORECASE)
GENERIC_555_PATTERN = re.compile(r"\b55[56]\s*(?:timer|timers|ic|chip|circuit)?\b", re.IGNORECASE)

DATASHEET_MARKERS = {
    "datasheet": 18,
    "data sheet": 18,
    "pin configuration": 18,
    "pin configurations": 18,
    "pinout": 18,
    "pinouts": 18,
    "pin number": 16,
    "pin functions": 18,
    "pin descriptions": 18,
    "signal descriptions": 12,
    "terminal functions": 16,
    "absolute maximum ratings": 14,
    "electrical characteristics": 14,
    "recommended operating conditions": 12,
    "ordering information": 8,
    "package information": 8,
    "package dimensions": 8,
    "block diagram": 6,
}

BOOK_NEGATIVE_MARKERS = {
    "published by": 12,
    "isbn": 12,
    "foreword": 8,
    "chapter": 7,
    "editor": 7,
    "magazine": 7,
    "this book": 7,
    "all rights reserved": 6,
    "for dummies": 8,
    "for makers": 8,
    "hackspace": 6,
}

SCHEMATIC_MARKERS = ("schematic", "circuit diagram", "wiring diagram", "netlist")
PROJECT_MARKERS = ("project", "build", "experiment", "breadboard", "parts list", "chapter")


@dataclass(frozen=True)
class ComponentCandidate:
    value: str
    count: int
    in_filename: bool


def classify_document(path: str, pages: Iterable[ExtractedPage] | Iterable[str]) -> DocumentProfile:
    page_texts = [page.text if isinstance(page, ExtractedPage) else str(page or "") for page in pages]
    sample = "\n".join(page_texts[:24])[:30000]
    filename = os.path.splitext(os.path.basename(path))[0]
    haystack = f"{filename}\n{sample}"
    lower = haystack.lower()

    candidates = detect_component_candidates(filename, sample)
    candidate = candidates[0] if candidates else None
    positive = 0
    reasons: list[str] = []
    for marker, score in DATASHEET_MARKERS.items():
        if marker in lower:
            positive += score
            reasons.append(marker)
    if "datasheet" in filename.lower() or "data sheet" in filename.lower():
        positive += 20
        reasons.append("filename:datasheet")
    if candidate:
        positive += 20 if candidate.in_filename else 10
        reasons.append(f"component:{candidate.value}")

    negative = 0
    negative_signals: list[str] = []
    for marker, score in BOOK_NEGATIVE_MARKERS.items():
        if marker in lower:
            negative += score
            negative_signals.append(marker)

    net_score = positive - min(negative, 35)
    if candidate and net_score >= 38:
        return DocumentProfile(
            document_type="component_datasheet",
            confidence=round(min(0.98, 0.45 + net_score / 100), 2),
            component_name=candidate.value,
            component_type=detect_component_type(candidate.value, sample),
            reasons=tuple(reasons[:8]),
            negative_signals=tuple(negative_signals[:8]),
        )

    if any(marker in lower for marker in SCHEMATIC_MARKERS):
        return DocumentProfile(
            document_type="schematic",
            confidence=0.72 if positive else 0.62,
            reasons=tuple(marker for marker in SCHEMATIC_MARKERS if marker in lower),
            negative_signals=tuple(negative_signals[:8]),
        )

    if any(marker in lower for marker in PROJECT_MARKERS):
        return DocumentProfile(
            document_type="project_or_reference",
            confidence=0.68,
            reasons=tuple(marker for marker in PROJECT_MARKERS if marker in lower),
            negative_signals=tuple(negative_signals[:8]),
        )

    if negative_signals:
        return DocumentProfile(
            document_type="reference_book",
            confidence=0.7,
            reasons=(),
            negative_signals=tuple(negative_signals[:8]),
        )

    return DocumentProfile(document_type="unknown", confidence=0.35)


def detect_component_candidates(filename: str, text: str) -> list[ComponentCandidate]:
    filename_text = filename.replace("_", " ").replace("-", " ")
    search_text = f"{filename_text}\n{text[:16000]}"
    filename_candidates = {_normalize_part(match.group(0)) for pattern in PART_PATTERNS for match in pattern.finditer(filename_text)}
    for match in FILENAME_PART_PATTERN.finditer(filename_text):
        candidate = _normalize_part(match.group(0))
        if is_plausible_component(candidate):
            filename_candidates.add(candidate)
    counts: Counter[str] = Counter()
    for pattern in PART_PATTERNS:
        for match in pattern.finditer(search_text):
            candidate = _normalize_part(match.group(0))
            if is_plausible_component(candidate):
                counts[candidate] += 1
    for candidate in filename_candidates:
        counts[candidate] += 2
    if GENERIC_555_PATTERN.search(filename_text) or re.search(r"\b555\s+timer\b", text[:6000], re.IGNORECASE):
        counts["NE555"] += 2
        if GENERIC_555_PATTERN.search(filename_text):
            filename_candidates.add("NE555")
    if GENERIC_555_PATTERN.search(filename_text) or re.search(r"\b556\s+timer\b", text[:6000], re.IGNORECASE):
        counts["LM556"] += 2
        if re.search(r"\b556\b", filename_text):
            filename_candidates.add("LM556")

    candidates = [
        ComponentCandidate(value=value, count=count, in_filename=value in filename_candidates)
        for value, count in counts.items()
        if is_plausible_component(value)
    ]
    candidates.sort(key=lambda item: (item.in_filename, item.count, len(item.value)), reverse=True)
    return candidates


def detect_component_type(component_name: str, text: str) -> str:
    name = (component_name or "").upper()
    if name.startswith(("ESP32", "ATMEGA", "ATTINY", "RP2040")):
        return "microcontroller"
    if name.startswith(("MCP23", "PCF857", "PCA95")):
        return "GPIO expander"
    if name.startswith(("ADS", "MCP30", "MCP32")):
        return "analog-to-digital converter"
    if name.startswith(("SSD13", "MAX72")):
        return "display controller"
    if name.startswith(("BMP", "BME", "DHT", "DS18")):
        return "sensor"
    if name.startswith(("L293", "L298", "TB66", "DRV", "ULN", "A4988")):
        return "motor driver"
    if name.startswith(("L78", "L79")):
        return "voltage regulator"
    if name.startswith(("74HC", "74HCT", "74LS", "CD4", "SN74")):
        return "logic IC"
    if name.startswith(("NE555", "LM555", "LM556", "NE556")):
        return "timer"
    if name.startswith("4N"):
        return "optocoupler"
    if name.startswith(("1N",)):
        return "diode"
    if name.startswith(("2N", "BC")):
        return "transistor"
    if name.startswith(("IRF", "IRL")):
        return "mosfet"

    haystack = f"{component_name} {text[:12000]}".lower()
    rules = [
        ("optocoupler", ("optocoupler", "opto-coupler", "phototransistor", "isolation")),
        ("timer", ("555", "556", "monostable", "astable", "timer")),
        ("analog-to-digital converter", ("analog-to-digital", "adc", "a/d converter", "conversion register")),
        ("display controller", ("oled", "display controller", "segment driver")),
        ("sensor", ("pressure sensor", "temperature sensor", "humidity sensor", "sensor")),
        ("microcontroller", ("microcontroller", "gpio", "pwm", "uart", "spi", "i2c")),
        ("voltage regulator", ("voltage regulator", "linear regulator", "ldo")),
        ("op amp", ("operational amplifier", "op amp", "op-amp")),
        ("mosfet", ("mosfet", "gate", "drain", "source")),
        ("transistor", ("transistor", "collector", "emitter", "base")),
        ("logic IC", ("shift register", "logic", "flip-flop", "counter", "decoder")),
    ]
    for component_type, keywords in rules:
        if any(keyword in haystack for keyword in keywords):
            return component_type
    return "component"


def _normalize_part(value: str) -> str:
    normalized = re.sub(r"[\s_-]+", "", value or "").upper()
    if normalized == "555":
        return "NE555"
    if normalized == "556":
        return "LM556"
    return normalized


def is_plausible_component(candidate: str) -> bool:
    if not candidate or len(candidate) < 3:
        return False
    if candidate in {"NEEDS", "INPUT", "OUTPUT", "COMMON", "ABSOLUTE", "MAXIMUM", "EDITOR", "CHAPTER"}:
        return False
    if candidate.startswith(("DOCID", "REV", "DATE", "TABLE", "FIGURE", "PAGE")):
        return False
    if re.fullmatch(r"DS0\d{3,}", candidate):
        return False
    if not any(char.isdigit() for char in candidate):
        return False
    if re.fullmatch(r"(?:19|20)\d{2}", candidate):
        return False
    return True
