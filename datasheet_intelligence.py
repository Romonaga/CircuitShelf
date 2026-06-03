"""Deterministic datasheet fact extraction for CircuitShelf."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable

from backend.ingestion.document_classifier import classify_document, detect_component_candidates, detect_component_type
from backend.ingestion.models import ExtractedPage
from pinout_extractor import extract_pinout_map


DATASHEET_INTELLIGENCE_VERSION = 2
PACKAGE_PATTERN = re.compile(r"\b(?:DIP|PDIP|SOIC|SOP|SOT-23|TO-92|TO-220|DIP-\d+|SO-\d+|DIP\d+)\b", re.IGNORECASE)
VOLTAGE_RANGE_PATTERN = re.compile(
    r"\b(?P<label>VCC|VDD|supply voltage|operating voltage|input voltage|output voltage)"
    r"[^.\n]{0,90}?(?P<low>-?\d+(?:\.\d+)?)\s*V?\s*(?:to|-|–)\s*(?P<high>-?\d+(?:\.\d+)?)\s*V\b",
    re.IGNORECASE,
)
SINGLE_VOLTAGE_PATTERN = re.compile(
    r"\b(?P<label>supply voltage|operating voltage|collector-emitter voltage|forward voltage)"
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
    profile = _profile_for_items(source, display_name, items)
    if not profile.is_component_datasheet:
        return _non_component_payload(source, display_name, profile)

    component_name = profile.component_name
    component_type = profile.component_type or detect_component_type(component_name, combined_text)
    facts = _dedupe_facts(
        _extract_packages(items)
        + _extract_voltage_facts(items)
        + _extract_current_facts(items)
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
        "confidence": max(confidence, profile.confidence),
        "facts": facts,
        "pinout": pinout,
        "documentType": profile.document_type,
        "profileReasons": list(profile.reasons),
        "extractorVersion": DATASHEET_INTELLIGENCE_VERSION,
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


def _profile_for_items(source: str, display_name: str | None, items: list[TextItem]):
    pages = [ExtractedPage(page_number=item.page or index + 1, text=item.text) for index, item in enumerate(items[:80])]
    profile = classify_document(display_name or source, pages)
    if profile.is_component_datasheet:
        return profile

    # Some reviews only pass the first page of a short datasheet. A strong filename
    # candidate plus pin evidence is still enough to build intelligence.
    combined_text = "\n".join(item.text for item in items[:12])
    candidates = detect_component_candidates(display_name or source, combined_text)
    pinout = extract_pinout_map([item.text for item in items], [_item_meta(item) for item in items], source)
    if candidates and pinout.get("pins"):
        candidate = candidates[0]
        return type(profile)(
            document_type="component_datasheet",
            confidence=max(profile.confidence, 0.78),
            component_name=candidate.value,
            component_type=detect_component_type(candidate.value, combined_text),
            reasons=tuple(list(profile.reasons) + [f"pinout:{len(pinout['pins'])}"]),
            negative_signals=profile.negative_signals,
        )
    return profile


def _non_component_payload(source: str, display_name: str | None, profile) -> dict:
    return {
        "source": source,
        "displayName": display_name or os.path.basename(source),
        "componentName": "",
        "componentType": profile.document_type,
        "summary": "",
        "confidence": profile.confidence,
        "facts": [],
        "pinout": {"source": source, "displayName": display_name or os.path.basename(source), "pins": []},
        "documentType": profile.document_type,
        "profileReasons": list(profile.reasons),
        "extractorVersion": DATASHEET_INTELLIGENCE_VERSION,
    }


def _item_meta(item: TextItem) -> dict:
    return {
        "source": item.source,
        "parent_source": item.source,
        "page": item.page,
        "db_chunk_index": item.chunk_index,
    }


def _extract_packages(items: Iterable[TextItem]) -> list[dict]:
    facts = []
    for item in items:
        for match in PACKAGE_PATTERN.finditer(item.text):
            facts.append(_fact("package", "Package", match.group(0).upper(), "", item, match.group(0)))
    return facts


def _extract_voltage_facts(items: Iterable[TextItem]) -> list[dict]:
    facts = []
    for item in items:
        range_spans = []
        for match in VOLTAGE_RANGE_PATTERN.finditer(item.text):
            value = f"{match.group('low')} to {match.group('high')}"
            facts.append(_fact("voltage", _clean_label(match.group("label")), value, "V", item, match.group(0)))
            range_spans.append(match.span())
        for match in SINGLE_VOLTAGE_PATTERN.finditer(item.text):
            if any(start <= match.start() <= end for start, end in range_spans):
                continue
            if _looks_like_plot_axis_or_test_condition(match.group(0)):
                continue
            facts.append(_fact("voltage", _clean_label(match.group("label")), match.group("value"), "V", item, match.group(0)))
    return facts


def _extract_current_facts(items: Iterable[TextItem]) -> list[dict]:
    facts = []
    for item in items:
        for match in CURRENT_PATTERN.finditer(item.text):
            facts.append(_fact("current", _clean_label(match.group("label")), match.group("value"), match.group("unit"), item, match.group(0)))
    return facts


def _extract_warnings(items: Iterable[TextItem]) -> list[dict]:
    facts = []
    keywords = ("do not exceed", "damage", "electrostatic", "esd", "derate")
    for item in items:
        snippet = _warning_snippet(item.text, keywords)
        if snippet and not _looks_like_legal_or_ordering_note(snippet):
            facts.append(_fact("warning", "Caution", snippet[:180], "", item, snippet))
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
    facts = sorted(facts, key=lambda fact: 0 if " to " in str(fact.get("value", "")) else 1)
    has_voltage_range = any(fact["type"] == "voltage" and " to " in str(fact.get("value", "")) for fact in facts)
    per_type_limits = {
        "package": 6,
        "voltage": 5,
        "current": 4,
        "warning": 4,
    }
    per_type_counts: dict[str, int] = {}
    result = []
    for fact in facts:
        fact_type = fact["type"]
        if has_voltage_range and _is_redundant_single_supply_voltage(fact):
            continue
        if per_type_counts.get(fact_type, 0) >= per_type_limits.get(fact_type, 4):
            continue
        key = (fact["type"], fact["label"].lower(), fact["value"].lower())
        if key in seen:
            continue
        seen.add(key)
        per_type_counts[fact_type] = per_type_counts.get(fact_type, 0) + 1
        result.append(fact)
        if len(result) >= 24:
            break
    return result


def _is_redundant_single_supply_voltage(fact: dict) -> bool:
    if fact.get("type") != "voltage":
        return False
    if " to " in str(fact.get("value", "")):
        return False
    label = str(fact.get("label") or "").upper()
    return label in {"SUPPLY VOLTAGE", "OPERATING VOLTAGE", "VCC", "VDD"}


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


def _warning_snippet(text: str, keywords: Iterable[str]) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    stress_match = re.search(r"\bStresses beyond[^.]{0,220}\.", normalized, re.IGNORECASE)
    if stress_match:
        return stress_match.group(0).strip()
    return _sentence_with_keywords(normalized, keywords)


def _looks_like_plot_axis_or_test_condition(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(
        marker in lowered
        for marker in (
            "pulse duration",
            "relative to",
            "propagation delay",
            "voltage drop",
            "output low",
            "output high",
            "no load",
        )
    )


def _looks_like_legal_or_ordering_note(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(
        marker in lowered
        for marker in (
            "rohs",
            "disclaims responsibility",
            "warranty",
            "intellectual property",
            "orderable",
            "package option addendum",
            "value unit",
        )
    )


def _clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().upper()


def _optional_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
