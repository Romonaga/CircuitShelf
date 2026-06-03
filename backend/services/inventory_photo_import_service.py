from __future__ import annotations

from collections import OrderedDict
from typing import Any

from db.lab_inventory import normalize_part_name
from inventory_import import dedupe_strings


PART_TYPES = {
    "component",
    "ic",
    "resistor",
    "capacitor",
    "diode",
    "transistor",
    "sensor",
    "module",
    "board",
    "display",
    "tooling",
    "power",
}


class InventoryPhotoImportService:
    def __init__(self, openai_assist_service: Any, logger: Any = None):
        self.openai_assist_service = openai_assist_service
        self.logger = logger

    def preview(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        note: str,
        entity_id: int | None,
        user_id: int | None,
        existing_parts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        result = self.openai_assist_service.identify_inventory_photo(
            image_bytes=image_bytes,
            mime_type=mime_type,
            note=note,
            entity_id=entity_id,
            user_id=user_id,
        )
        if not result:
            raise ValueError("OpenAI inventory photo import is not enabled for this user or entity.")
        items = self._items_from_model(result.get("items") or [], existing_parts)
        return {
            "items": items,
            "count": len(items),
            "source": "photo",
            "model": result.get("model"),
            "paidBy": result.get("paidBy"),
            "estimatedCost": result.get("estimatedCost"),
        }

    def _items_from_model(self, raw_items: list[Any], existing_parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        existing_index = self._existing_index(existing_parts)
        result: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for raw in raw_items[:80]:
            if not isinstance(raw, dict):
                continue
            display_name = str(raw.get("displayName") or raw.get("name") or "").strip()[:120]
            if not display_name:
                continue
            aliases = dedupe_strings([str(alias) for alias in raw.get("aliases") or []])
            normalized = normalize_part_name(display_name)
            existing = existing_index.get(normalized)
            if not existing:
                for alias in aliases:
                    existing = existing_index.get(normalize_part_name(alias))
                    if existing:
                        break
            part_type = str(raw.get("partType") or raw.get("type") or "component").strip().lower()
            if part_type not in PART_TYPES:
                part_type = "component"
            quantity = self._quantity(raw.get("quantity"))
            warnings = dedupe_strings([str(warning) for warning in raw.get("warnings") or []])
            confidence = self._confidence(raw.get("confidence"))
            if confidence < 0.6:
                warnings = dedupe_strings([*warnings, "Low confidence visual identification; verify before importing."])
            item = {
                "rawLine": f"photo: {display_name}",
                "displayName": display_name,
                "normalizedName": normalized,
                "partType": part_type,
                "quantity": quantity,
                "location": "",
                "locationId": None,
                "notes": str(raw.get("notes") or "").strip()[:1000],
                "aliases": aliases,
                "confidence": confidence,
                "warnings": warnings,
                "action": "merge" if existing else "create",
                "existingPartId": existing.get("id") if existing else None,
            }
            key = str(item["existingPartId"] or normalized)
            current = result.get(key)
            if current:
                current["quantity"] = int(current["quantity"]) + quantity
                current["aliases"] = dedupe_strings([*current.get("aliases", []), *aliases])
                current["warnings"] = dedupe_strings([*current.get("warnings", []), *warnings])
                continue
            result[key] = item
        return list(result.values())

    @staticmethod
    def _existing_index(existing_parts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for part in existing_parts or []:
            index[normalize_part_name(part.get("displayName") or "")] = part
            for alias in part.get("aliases") or []:
                index[normalize_part_name(alias)] = part
        return {key: value for key, value in index.items() if key}

    @staticmethod
    def _quantity(value: Any) -> int:
        try:
            return max(1, min(10000, int(float(value or 1))))
        except Exception:
            return 1

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.5
