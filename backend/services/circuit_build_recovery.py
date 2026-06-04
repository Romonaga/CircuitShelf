"""LLM recovery prompt and parser for CircuitShelf build cards."""

from __future__ import annotations

import json
import re
from collections import OrderedDict


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


def _dedupe_dicts(items: list[dict], key: str) -> list[dict]:
    result = OrderedDict()
    for item in items:
        result.setdefault(item.get(key), item)
    return list(result.values())


def _dedupe_strings(items: list[str]) -> list[str]:
    return list(OrderedDict((item, None) for item in items).keys())
