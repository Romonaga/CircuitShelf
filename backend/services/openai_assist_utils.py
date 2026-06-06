from __future__ import annotations

import json
import re
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = _json_candidate(text)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {"raw": parsed}
    except Exception:
        return {"raw": text[:4000]}


def _json_candidate(text: str) -> str:
    cleaned = str(text or "").strip()
    fence_match = re.match(r"^```(?:json)?\s*(?P<body>.*?)\s*```$", cleaned, re.IGNORECASE | re.DOTALL)
    if fence_match:
        cleaned = fence_match.group("body").strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def compact_intelligence_for_prompt(intelligence: dict[str, Any]) -> dict[str, Any]:
    pinout = intelligence.get("pinout") or {}
    return {
        "componentName": intelligence.get("componentName") or "",
        "componentType": intelligence.get("componentType") or "",
        "summary": intelligence.get("summary") or "",
        "confidence": intelligence.get("confidence"),
        "factCount": len(intelligence.get("facts") or []),
        "pinCount": len(pinout.get("pins") or []),
        "pins": [
            {
                "pin": pin.get("pin"),
                "label": pin.get("label"),
                "function": pin.get("function"),
                "page": pin.get("page"),
            }
            for pin in (pinout.get("pins") or [])[:32]
        ],
    }
