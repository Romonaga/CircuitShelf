"""Deterministic datasheet fact extraction for CircuitShelf."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable

from pinout_extractor import extract_pinout_map


PART_PATTERNS = [
    re.compile(r"\b(?:NE|LM|TL|SN|ATmega|ATtiny|PC|TLP|CD|74HC|74LS|2N|BC|IRF|IRL)\s?-?[A-Z0-9]{2,8}\b", re.IGNORECASE),
    re.compile(r"\bL\d{2,5}[A-Z0-9]*\b", re.IGNORECASE),
    re.compile(r"\b4N(?:25|26|27|28|32|33|35|36|37)\b", re.IGNORECASE),
    re.compile(r"\b(?:555|556)\s*(?:timer)?\b", re.IGNORECASE),
]

PACKAGE_PATTERN = re.compile(r"\b(?:DIP|PDIP|SOIC|SOP|SOT-23|TO-92|TO-220|DIP-\d+|SO-\d+|DIP\d+)\b", re.IGNORECASE)
VOLTAGE_RANGE_PATTERN = re.compile(
    r"\b(?P<label>VCC|VDD|supply voltage|operating voltage|input voltage|output voltage)"
    r"[^.\n]{0,90}?(?P<low>-?\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(?P<high>-?\d+(?:\.\d+)?)\s*V\b",
    re.IGNORECASE,
)
SINGLE_VOLTAGE_PATTERN = re.compile(
    r"\b(?P<label>VCC|VDD|supply voltage|operating voltage|collector-emitter voltage|forward voltage)"
    r"[^.\n]{0,90}?(?P<value>-?\d+(?:\.\d+)?)\s*V\b",
    re.IGNORECASE,
)
CURRENT_PATTERN = re.compile(
    r"\b(?P<label>output current|forward current|supply current|collector current)"
    r"[^.\n]{0,90}?(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mA|A|uA|µA)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TextItem:
    text: str
    source: str
    page: int | None
    chunk_index: int | None


def build_datasheet_intelligence(chunks: list[str], metadata: list[dict], source: str, display_name: str | None = None) -> dict:
    items = _text_items(chunks, metadata, source)
    combined_text = "\n".join(item.text for item in items[:40])
    component_name = _detect_component_name(display_name or source, combined_text)
    component_type = _detect_component_type(combined_text, component_name)
    facts = _dedupe_facts(
        _extract_packages(items)
        + _extract_voltage_facts(items)
        + _extract_current_facts(items)
        + _extract_applications(items)
        + _extract_warnings(items)
    )
    pinout = extract_pinout_map(chunks, metadata, source)
    summary = _summary(component_name, component_type, facts, pinout)
    confidence = _confidence(component_name, facts, pinout)

    return {
        "source": source,
        "displayName": display_name or os.path.basename(source),
        "componentName": component_name,
        "componentType": component_type,
        "summary": summary,
        "confidence": confidence,
        "facts": facts,
        "pinout": pinout,
    }


def _text_items(chunks: list[str], metadata: list[dict], source: str) -> list[TextItem]:
    items = []
    for index, text in enumerate(chunks):
        meta = metadata[index] if index < len(metadata) else {}
        candidate_source = meta.get("parent_source") or meta.get("source") or source
        if candidate_source != source:
            continue
        stripped = re.sub(r"\s+", " ", text or "").strip()
        if not stripped:
            continue
        items.append(
            TextItem(
                text=stripped,
                source=source,
                page=_optional_int(meta.get("page")),
                chunk_index=_optional_int(meta.get("db_chunk_index", index)),
            )
        )
    return items


def _detect_component_name(display_name: str, text: str) -> str:
    base = os.path.splitext(os.path.basename(display_name))[0]
    candidates = []
    for pattern in PART_PATTERNS:
        candidates.extend(match.group(0).replace(" ", "").upper() for match in pattern.finditer(f"{base}\n{text[:4000]}"))
    for candidate in candidates:
        if candidate not in {"DIP", "SOIC"}:
            return candidate
    return base


def _detect_component_type(text: str, component_name: str) -> str:
    haystack = f"{component_name} {text[:8000]}".lower()
    rules = [
        ("optocoupler", ("optocoupler", "opto-coupler", "phototransistor", "isolation")),
        ("timer", ("555", "timer", "monostable", "astable")),
        ("microcontroller", ("microcontroller", "gpio", "adc", "pwm", "arduino")),
        ("voltage regulator", ("voltage regulator", "linear regulator", "ldo")),
        ("op amp", ("operational amplifier", "op amp", "op-amp")),
        ("transistor", ("transistor", "collector", "emitter", "base")),
        ("mosfet", ("mosfet", "gate", "drain", "source")),
    ]
    for component_type, keywords in rules:
        if any(keyword in haystack for keyword in keywords):
            return component_type
    return "component"


def _extract_packages(items: Iterable[TextItem]) -> list[dict]:
    facts = []
    for item in items:
        for match in PACKAGE_PATTERN.finditer(item.text):
            facts.append(_fact("package", "Package", match.group(0).upper(), "", item, match.group(0)))
    return facts


def _extract_voltage_facts(items: Iterable[TextItem]) -> list[dict]:
    facts = []
    for item in items:
        for match in VOLTAGE_RANGE_PATTERN.finditer(item.text):
            value = f"{match.group('low')} to {match.group('high')}"
            facts.append(_fact("voltage", _clean_label(match.group("label")), value, "V", item, match.group(0)))
        for match in SINGLE_VOLTAGE_PATTERN.finditer(item.text):
            facts.append(_fact("voltage", _clean_label(match.group("label")), match.group("value"), "V", item, match.group(0)))
    return facts


def _extract_current_facts(items: Iterable[TextItem]) -> list[dict]:
    facts = []
    for item in items:
        for match in CURRENT_PATTERN.finditer(item.text):
            facts.append(_fact("current", _clean_label(match.group("label")), match.group("value"), match.group("unit"), item, match.group(0)))
    return facts


def _extract_applications(items: Iterable[TextItem]) -> list[dict]:
    facts = []
    for item in items:
        lower = item.text.lower()
        if "application" not in lower and "typical" not in lower:
            continue
        snippet = _sentence_with_keywords(item.text, ("application", "typical", "circuit"))
        if snippet:
            facts.append(_fact("application", "Application", snippet[:160], "", item, snippet))
    return facts


def _extract_warnings(items: Iterable[TextItem]) -> list[dict]:
    facts = []
    keywords = ("absolute maximum", "do not exceed", "damage", "isolation", "current limiting", "derate")
    for item in items:
        snippet = _sentence_with_keywords(item.text, keywords)
        if snippet:
            fact_type = "absolute_maximum" if "absolute maximum" in snippet.lower() else "warning"
            facts.append(_fact(fact_type, "Caution", snippet[:180], "", item, snippet))
    return facts


def _fact(fact_type: str, label: str, value: str, unit: str, item: TextItem, evidence: str) -> dict:
    return {
        "type": fact_type,
        "label": label.strip(),
        "value": re.sub(r"\s+", " ", str(value)).strip(),
        "unit": unit,
        "page": item.page,
        "chunkIndex": item.chunk_index,
        "evidence": re.sub(r"\s+", " ", evidence).strip()[:320],
        "confidence": 0.85,
    }


def _dedupe_facts(facts: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for fact in facts:
        key = (fact["type"], fact["label"].lower(), fact["value"].lower(), fact.get("page"))
        if key in seen:
            continue
        seen.add(key)
        result.append(fact)
        if len(result) >= 24:
            break
    return result


def _summary(component_name: str, component_type: str, facts: list[dict], pinout: dict) -> str:
    pieces = [f"{component_name} appears to be a {component_type}."]
    if pinout.get("pins"):
        pieces.append(f"Detected {len(pinout['pins'])} pin assignments.")
    voltage = next((fact for fact in facts if fact["type"] == "voltage"), None)
    if voltage:
        pieces.append(f"{voltage['label']}: {voltage['value']} {voltage['unit']}".strip())
    return " ".join(pieces)


def _confidence(component_name: str, facts: list[dict], pinout: dict) -> float:
    score = 0.35
    if component_name:
        score += 0.15
    if pinout.get("pins"):
        score += 0.25
    if facts:
        score += min(0.25, len(facts) * 0.03)
    return round(min(score, 0.97), 2)


def _sentence_with_keywords(text: str, keywords: Iterable[str]) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        lower = sentence.lower()
        if any(keyword in lower for keyword in keywords):
            return sentence.strip()
    return ""


def _clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().upper()


def _optional_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
