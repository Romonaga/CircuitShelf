from __future__ import annotations

import json
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"raw": parsed}
    except Exception:
        return {"raw": text[:4000]}


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
