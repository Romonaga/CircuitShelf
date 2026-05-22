"""Build-card generation from retrieved electronics sources."""

from __future__ import annotations

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
    wiring = _specific_wiring(lower, pins) or _pinout_wiring(pins)
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
    if "555" in lower or "timer" in component_type:
        parts.extend(
            [
                {"name": "Timing resistor(s)", "detail": "Example: 10 kOhm and 100 kOhm."},
                {"name": "Timing capacitor", "detail": "Example: 10 uF for a slow blink."},
                {"name": "0.01 uF capacitor", "detail": "Use on the control-voltage pin."},
            ]
        )
    return _dedupe_dicts(parts, "name")


def _specific_wiring(lower: str, pins: list[dict]) -> list[dict]:
    if "4n35" in lower or "optocoupler" in lower:
        return [
            _wire("Pin 1 Anode", "MCU output through 220 Ohm to 1 kOhm resistor", "Input LED current must be limited.", pins, 1),
            _wire("Pin 2 Cathode", "MCU ground", "Completes the input LED circuit.", pins, 2),
            _wire("Pin 3 NC", "Leave unconnected", "No internal connection.", pins, 3),
            _wire("Pin 4 Emitter", "Isolated output ground", "Do not assume this ground must be tied to MCU ground.", pins, 4),
            _wire("Pin 5 Collector", "Output load or input pull-up", "Use a pull-up resistor to the output-side supply.", pins, 5),
            _wire("Pin 6 Base", "Usually leave open", "Only bias this pin when the datasheet/application note calls for it.", pins, 6),
        ]
    if "555" in lower or "timer" in lower:
        return [
            _wire("Pin 1 GND", "Ground rail", "Common circuit ground.", pins, 1),
            _wire("Pin 8 VCC", "+5 V to +15 V supply", "Use the voltage range supported by your specific 555 variant.", pins, 8),
            _wire("Pin 4 RESET", "VCC", "Tie high unless you need external reset control.", pins, 4),
            _wire("Pin 5 CTRL", "0.01 uF capacitor to ground", "Stabilizes the threshold reference.", pins, 5),
            _wire("Pin 2 TRIG", "Tie to Pin 6 for astable mode", "This timing node connects to the timing capacitor.", pins, 2),
            _wire("Pin 6 THRES", "Tie to Pin 2 and timing capacitor", "The capacitor voltage is measured here.", pins, 6),
            _wire("Pin 7 DISCH", "Between timing resistors", "Discharges the timing capacitor each cycle.", pins, 7),
            _wire("Pin 3 OUT", "LED plus series resistor or logic input", "Do not drive an LED without a resistor.", pins, 3),
        ]
    return []


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
