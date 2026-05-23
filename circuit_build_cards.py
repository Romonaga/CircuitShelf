"""Build-card generation from retrieved electronics sources."""

from __future__ import annotations

import json
import re
import os
from collections import OrderedDict


DIRECT_BUILD_INTENT_PATTERN = re.compile(
    r"\b(wire|wiring|connect|hook\s*up|breadboard|pinout|schematic)\b",
    re.IGNORECASE,
)
BUILD_CARD_REQUEST_PATTERN = re.compile(
    r"\b(build|bench|wiring|assembly|project)\s*card\b|\bcard\s+for\b",
    re.IGNORECASE,
)
BUILD_ACTION_PATTERN = re.compile(r"\b(build|make|create|assemble)\b", re.IGNORECASE)
BUILD_CONTEXT_PATTERN = re.compile(
    r"\b("
    r"arduino|raspberry|gpio|555|timer|op[\s-]?amp|optocoupler|transistor|mosfet|led|relay|sensor|"
    r"adc|dac|ic|chip|pin|pins|datasheet|circuit|schematic|diagram|breadboard|"
    r"[a-z]{1,8}\d{2,}[a-z0-9-]*|\d{3,}[a-z0-9-]*"
    r")\b",
    re.IGNORECASE,
)
PROJECT_RECOMMENDATION_PATTERN = re.compile(
    r"("
    r"\b(good|beginner|starter|first|simple|easy|recommend|suggest|idea|ideas)\b.{0,80}\bproject\b|"
    r"\bproject\b.{0,80}\b(good|beginner|starter|first|simple|easy|recommend|suggest|idea|ideas)\b"
    r")",
    re.IGNORECASE,
)


def should_build_card(question: str) -> bool:
    text = question or ""
    if BUILD_CARD_REQUEST_PATTERN.search(text):
        return True
    if PROJECT_RECOMMENDATION_PATTERN.search(text):
        return False
    if DIRECT_BUILD_INTENT_PATTERN.search(text):
        return True
    return bool(BUILD_ACTION_PATTERN.search(text) and BUILD_CONTEXT_PATTERN.search(text))


def build_circuit_build_card(
    question: str,
    source_payload: list[dict],
    intelligence_by_source: dict[str, dict],
    *,
    context_question: str | None = None,
) -> dict | None:
    if not should_build_card(question):
        return None

    ranking_question = context_question or question
    intelligence = _first_intelligence(ranking_question, source_payload, intelligence_by_source)
    if not intelligence:
        return None

    component = intelligence.get("componentName") or intelligence.get("displayName") or "component"
    component_type = intelligence.get("componentType") or "component"
    lower = f"{ranking_question} {component} {component_type}".lower()
    pins = intelligence.get("pinout", {}).get("pins", [])
    wiring = _pinout_wiring(pins)
    facts = intelligence.get("facts", [])

    return {
        "title": f"{component} build card",
        "componentName": component,
        "componentType": component_type,
        "summary": intelligence.get("summary", ""),
        "confidence": intelligence.get("confidence", 0),
        "parts": _parts(lower, component, component_type),
        "power": _power_notes(facts),
        "wiring": wiring,
        "checks": _checks(component_type, wiring),
        "warnings": _warnings(facts, component_type),
        "sourceNotes": _source_notes(source_payload, intelligence),
    }


RECOVERY_SYSTEM_PROMPT = (
    "You are CircuitShelf's build-card recovery engine. Convert electronics answers "
    "and retrieved source summaries into strict JSON bench build cards. Do not use a "
    "fixed recipe for any specific chip. Use only the concrete details in the provided "
    "answer, source summaries, and ordinary low-voltage hobby safety rules. If exact "
    "pinouts, voltages, or component values are not supported, put that uncertainty in "
    "warnings or return null when a usable plan cannot be made. Return JSON only."
)


def build_recovery_prompt(question: str, answer: str, source_payload: list[dict]) -> str:
    sources = []
    for source in (source_payload or [])[:8]:
        chunks = []
        for chunk in source.get("chunks") or []:
            chunks.append(
                {
                    "page": chunk.get("page"),
                    "section": chunk.get("section"),
                    "preview": str(chunk.get("preview") or "")[:420],
                }
            )
        sources.append(
            {
                "source": source.get("source"),
                "displayName": source.get("displayName"),
                "pages": source.get("pages") or [],
                "chunkCount": source.get("chunkCount") or 0,
                "chunks": chunks[:4],
            }
        )

    payload = {
        "objective": question,
        "answer": str(answer or "")[:5000],
        "sources": sources,
        "schema": {
            "title": "short project title",
            "componentName": "main component or project family",
            "componentType": "component category",
            "summary": "one paragraph",
            "confidence": 0.0,
            "parts": [{"name": "part", "detail": "why/value/package"}],
            "power": ["power note"],
            "wiring": [{"from": "pin/component/rail", "to": "pin/component/rail", "note": "specific instruction", "page": None}],
            "checks": ["verification step"],
            "warnings": ["safety or uncertainty warning"],
            "sourceNotes": [{"source": "source path/name", "pages": [1], "chunks": 1}],
        },
    }
    return (
        "Create one build card JSON object for this electronics project. The card must be "
        "generic to the requested objective; do not force a 555, Arduino, MOSFET, op-amp, "
        "or any other component unless the objective or answer actually calls for it. "
        "Prefer pin-by-pin wiring rows when the answer/source supports them. If a safe, "
        "concrete bench plan cannot be formed, return exactly null.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def parse_recovered_build_card(raw: str, source_payload: list[dict]) -> dict | None:
    data = _extract_json_value(raw)
    if not isinstance(data, dict):
        return None

    card = {
        "title": _clean_text(data.get("title"), 100) or "Assembly plan",
        "componentName": _clean_text(data.get("componentName"), 100) or _clean_text(data.get("component"), 100) or "Project",
        "componentType": _clean_text(data.get("componentType"), 80) or _clean_text(data.get("type"), 80) or "project",
        "summary": _clean_text(data.get("summary"), 900),
        "confidence": _bounded_float(data.get("confidence"), 0.45),
        "parts": _normalize_parts(data.get("parts")),
        "power": _normalize_strings(data.get("power"), 8),
        "wiring": _normalize_wiring(data.get("wiring")),
        "checks": _normalize_strings(data.get("checks"), 12),
        "warnings": _normalize_strings(data.get("warnings"), 8),
        "sourceNotes": _normalize_source_notes(data.get("sourceNotes"), source_payload),
    }
    if len(card["parts"]) < 1 or len(card["wiring"]) < 2:
        return None
    if not card["checks"]:
        card["checks"] = ["Verify every power and ground connection before applying power."]
    if not card["warnings"]:
        card["warnings"] = ["Verify the plan against cited source material before powering the circuit."]
    return card


def _extract_json_value(raw: str):
    text = str(raw or "").strip()
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    for candidate in _json_candidates(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _json_candidates(text: str) -> list[str]:
    candidates = [text]
    for start, end in [("{", "}"), ("[", "]")]:
        left = text.find(start)
        right = text.rfind(end)
        if left >= 0 and right > left:
            candidates.append(text[left:right + 1])
    return candidates


def _normalize_parts(value) -> list[dict]:
    rows = []
    for item in value or []:
        if isinstance(item, str):
            name = _clean_text(item, 120)
            detail = ""
        elif isinstance(item, dict):
            name = _clean_text(item.get("name") or item.get("part"), 120)
            detail = _clean_text(item.get("detail") or item.get("value") or item.get("note"), 220)
        else:
            continue
        if name:
            rows.append({"name": name, "detail": detail})
    return _dedupe_dicts(rows, "name")[:30]


def _normalize_wiring(value) -> list[dict]:
    rows = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        from_pin = _clean_text(item.get("from") or item.get("source") or item.get("pin"), 160)
        to = _clean_text(item.get("to") or item.get("destination") or item.get("connectTo"), 220)
        note = _clean_text(item.get("note") or item.get("why") or item.get("instruction"), 360)
        if from_pin and to:
            rows.append({"from": from_pin, "to": to, "note": note, "page": _optional_int(item.get("page"))})
    return rows[:40]


def _normalize_strings(value, limit: int) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return _dedupe_strings([_clean_text(item, 260) for item in value or [] if _clean_text(item, 260)])[:limit]


def _normalize_source_notes(value, source_payload: list[dict]) -> list[dict]:
    rows = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        source = _clean_text(item.get("source") or item.get("displayName"), 220)
        if source:
            rows.append({"source": source, "pages": _pages(item.get("pages")), "chunks": _optional_int(item.get("chunks")) or 0})
    if rows:
        return rows[:8]
    for source in (source_payload or [])[:5]:
        rows.append(
            {
                "source": source.get("displayName") or source.get("source") or "Retrieved source",
                "pages": _pages(source.get("pages")),
                "chunks": _optional_int(source.get("chunkCount")) or 0,
            }
        )
    return rows


def _pages(value) -> list[int]:
    if not isinstance(value, list):
        value = [value] if value is not None else []
    pages = []
    for item in value:
        page = _optional_int(item)
        if page is not None and page not in pages:
            pages.append(page)
    return pages[:12]


def _bounded_float(value, fallback: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback


def _optional_int(value):
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _first_intelligence(question: str, source_payload: list[dict], intelligence_by_source: dict[str, dict]) -> dict | None:
    candidates = list(intelligence_by_source.values())
    if not candidates:
        return None

    source_order = {
        source.get("source"): index
        for index, source in enumerate(source_payload or [])
        if source.get("source")
    }
    return max(
        candidates,
        key=lambda item: _intelligence_score(question, item, source_order),
    )


def _intelligence_score(question: str, intelligence: dict, source_order: dict[str, int]) -> tuple:
    component = str(intelligence.get("componentName") or intelligence.get("displayName") or "")
    display = str(intelligence.get("displayName") or "")
    source = str(intelligence.get("source") or "")
    haystack = _normalized_identifier(f"{component} {display} {source}")
    component_id = _normalized_identifier(component)
    terms = [_normalized_identifier(term) for term in _question_component_terms(question)]

    component_term_match = any(term and term in component_id for term in terms)
    source_term_match = any(term and term in haystack for term in terms)
    pin_count = len((intelligence.get("pinout") or {}).get("pins") or [])
    source_rank = source_order.get(source, 10_000)

    return (
        bool(component_term_match),
        bool(intelligence.get("questionMatch")),
        bool(source_term_match),
        pin_count,
        float(intelligence.get("confidence") or 0.0),
        -source_rank,
    )


def _question_component_terms(question: str) -> list[str]:
    return [match.group(0).strip("-") for match in re.finditer(r"\b[A-Za-z]*\d[A-Za-z0-9-]{1,24}\b", question or "")]


def _normalized_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _parts(lower: str, component: str, component_type: str) -> list[dict]:
    parts = [{"name": component, "detail": component_type}]
    if "arduino" in lower:
        parts.append({"name": "Arduino-compatible board", "detail": "Uses 5 V logic unless your board is 3.3 V."})
    if "raspberry" in lower or "gpio" in lower:
        parts.append({"name": "Raspberry Pi or GPIO board", "detail": "GPIO is 3.3 V only."})
    parts.extend(
        [
            {"name": "Breadboard and jumpers", "detail": "Keep power rails clear and labeled."},
            {"name": "Current-limiting resistors", "detail": "Use for LEDs and optocoupler inputs."},
            {"name": "Power supply", "detail": "Match the datasheet operating range."},
        ]
    )
    return _dedupe_dicts(parts, "name")


def _pinout_wiring(pins: list[dict]) -> list[dict]:
    rows = []
    for pin in pins[:16]:
        function = pin.get("function") or pin.get("label") or "Unknown"
        destination = _destination_for_function(function)
        rows.append(_wire(f"Pin {pin.get('pin')} {function}", destination, "Confirm against the cited datasheet page before powering.", pins, pin.get("pin")))
    return rows


def _destination_for_function(function: str) -> str:
    upper = function.upper()
    if upper in {"GND", "GROUND", "VSS"}:
        return "Ground rail"
    if upper in {"VCC", "VDD", "VIN"}:
        return "Positive supply rail"
    if "OUTPUT" in upper or upper == "OUT":
        return "Load, MCU input, or next stage"
    if "INPUT" in upper or upper in {"IN", "TRIG"}:
        return "Signal source or MCU output"
    if upper in {"NC", "NO CONNECTION"}:
        return "Leave unconnected"
    return "Use according to this pin function"


def _wire(from_pin: str, to: str, note: str, pins: list[dict], pin_number) -> dict:
    pin = next((item for item in pins if str(item.get("pin")) == str(pin_number)), {})
    return {
        "from": from_pin,
        "to": to,
        "note": note,
        "page": pin.get("page"),
    }


def _power_notes(facts: list[dict]) -> list[str]:
    notes = []
    for fact in facts:
        if fact.get("type") == "voltage":
            notes.append(f"{fact.get('label')}: {fact.get('value')} {fact.get('unit', '')}".strip())
    if not notes:
        notes.append("Use the operating voltage from the cited datasheet before applying power.")
    return notes[:5]


def _checks(component_type: str, wiring: list[dict]) -> list[str]:
    checks = [
        "Verify supply polarity before inserting the IC.",
        "Check continuity from each IC pin to its intended rail or signal.",
        "Power the circuit with current limiting for the first test.",
    ]
    if "optocoupler" in component_type:
        checks.append("Confirm whether the input and output grounds should stay isolated.")
    if any("LED" in row.get("to", "") or "LED" in row.get("note", "") for row in wiring):
        checks.append("Confirm every LED path has a current-limiting resistor.")
    return checks


def _warnings(facts: list[dict], component_type: str) -> list[str]:
    warnings = []
    for fact in facts:
        if fact.get("type") in {"warning", "absolute_maximum"}:
            warnings.append(fact.get("value") or fact.get("evidence") or "")
    if "optocoupler" in component_type:
        warnings.append("Isolation ratings depend on PCB spacing and package limits; do not use a breadboard for hazardous voltages.")
    if not warnings:
        warnings.append("Datasheet limits are not design targets; stay inside recommended operating conditions.")
    return [item for item in _dedupe_strings(warnings) if item][:5]


def _source_notes(source_payload: list[dict], intelligence: dict) -> list[dict]:
    notes = []
    source = intelligence.get("source")
    for item in source_payload:
        item_source = item.get("source") or ""
        if item_source == source or os.path.basename(item_source) == os.path.basename(source or ""):
            notes.append(
                {
                    "source": item.get("displayName") or item.get("source"),
                    "pages": item.get("pages") or [],
                    "chunks": item.get("chunkCount") or 0,
                }
            )
    return notes


def _dedupe_dicts(items: list[dict], key: str) -> list[dict]:
    result = OrderedDict()
    for item in items:
        result.setdefault(item.get(key), item)
    return list(result.values())


def _dedupe_strings(items: list[str]) -> list[str]:
    return list(OrderedDict((item, None) for item in items).keys())
