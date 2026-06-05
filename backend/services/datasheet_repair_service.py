from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Callable

from backend.ingestion.document_classifier import is_plausible_component
from backend.services.datasheet_intelligence import DATASHEET_INTELLIGENCE_VERSION


class DatasheetRepairService:
    def __init__(
        self,
        *,
        vector_store: Any,
        trace_logger: Any,
        config: dict | None,
        openai_assist_service: Any,
        rel_path: Callable[[str | None], str],
    ):
        self.vector_store = vector_store
        self.trace_logger = trace_logger
        self.config = config or {}
        self.openai_assist_service = openai_assist_service
        self.rel_path = rel_path

    def repair_if_needed(self, doc_name: str, chunks: list[str], metadata: list[dict], intelligence: dict) -> dict:
        if not self.should_try_openai_repair(intelligence):
            return intelligence
        if not self.openai_assist_service:
            return intelligence

        scope = self.source_ingest_scope(doc_name)
        try:
            result = self.openai_assist_service.repair_datasheet_intelligence(
                source_path=self.rel_path(doc_name),
                is_global=bool(scope["is_global"]),
                entity_id=scope.get("entity_id"),
                user_id=scope.get("created_by_user_id"),
                local_intelligence=intelligence,
                sample_text=self.repair_sample_text(chunks, metadata),
                enabled=True,
                decision_reason=self.repair_decision_reason(doc_name, intelligence),
            )
        except Exception as exc:
            self.trace_logger.warning(f"OpenAI datasheet repair failed for {doc_name}: {exc}")
            return intelligence

        repair = (result or {}).get("repair")
        if not isinstance(repair, dict):
            return intelligence
        merged = merge_datasheet_repair(intelligence, repair)
        if merged != intelligence:
            merged.setdefault("aiAssist", {})
            merged["aiAssist"].update({
                "provider": result.get("provider"),
                "model": result.get("model"),
                "paidBy": result.get("paidBy"),
                "estimatedCost": result.get("estimatedCost"),
                "reason": "deterministic_datasheet_repair",
            })
            self.trace_logger.info(f"🤖 OpenAI repaired datasheet intelligence for {doc_name}.")
        return merged

    def should_try_openai_repair(self, intelligence: dict) -> bool:
        if not self.config.get("DATASHEET_OPENAI_REPAIR_ENABLED", True):
            return False
        if not intelligence or intelligence.get("documentType") != "component_datasheet":
            return False
        component_name = str(intelligence.get("componentName") or "").strip()
        if not component_name or not is_plausible_component(component_name):
            return False
        pin_count = len((intelligence.get("pinout") or {}).get("pins") or [])
        fact_count = len(intelligence.get("facts") or [])
        confidence = optional_float(intelligence.get("confidence")) or 0.0
        return pin_count == 0 or fact_count < 2 or confidence < 0.82 or pinout_has_gaps(intelligence)

    def repair_decision_reason(self, doc_name: str, intelligence: dict) -> str:
        component_name = str(intelligence.get("componentName") or doc_name).strip()
        pin_count = len((intelligence.get("pinout") or {}).get("pins") or [])
        fact_count = len(intelligence.get("facts") or [])
        confidence = optional_float(intelligence.get("confidence")) or 0.0
        triggers: list[str] = []
        if pin_count == 0:
            triggers.append("no deterministic pinout was found")
        elif pinout_has_gaps(intelligence):
            triggers.append("deterministic pinout has missing pin numbers")
        if fact_count < 2:
            triggers.append(f"only {fact_count} deterministic facts were found")
        if confidence < 0.82:
            triggers.append(f"local confidence {confidence:.2f} is below 0.82")
        if not triggers:
            triggers.append("local datasheet intelligence needed enrichment")
        return f"Datasheet intelligence repair for {component_name}: {', '.join(triggers)}."

    def source_ingest_scope(self, source: str) -> dict:
        rel_path = self.rel_path(source)
        scope = self.vector_store.ingest_scope_overrides([rel_path]).get(rel_path)
        if not scope:
            scope = self.vector_store.document_scopes_for_sources([rel_path]).get(rel_path)
        is_global = bool(scope.get("is_global", True)) if scope else True
        return {
            "is_global": is_global,
            "entity_id": None if is_global else scope.get("entity_id"),
            "created_by_user_id": scope.get("created_by_user_id") if scope else None,
        }

    def repair_sample_text(self, chunks: list[str], metadata: list[dict], max_chars: int = 9000) -> str:
        scored: list[tuple[int, int, str]] = []
        for index, text in enumerate(chunks):
            cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            score = 0
            for marker in (
                "pin functions",
                "pin description",
                "pin descriptions",
                "pin configuration",
                "connection diagram",
                "terminal functions",
                "terminal assignments",
                "electrical characteristics",
                "recommended operating",
                "absolute maximum",
            ):
                if marker in lowered:
                    score += 5
            if re.search(r"\b(?:vcc|vdd|gnd|supply voltage|operating voltage|output current)\b", lowered):
                score += 2
            page = (metadata[index] if index < len(metadata) else {}).get("page")
            prefix = f"[chunk {index} page {page}] " if page else f"[chunk {index}] "
            scored.append((score, index, prefix + cleaned[:1400]))

        prioritized = sorted(scored, key=lambda item: (-item[0], item[1]))
        selected: list[str] = []
        total = 0
        for score, _index, text in prioritized:
            if score <= 0 and selected:
                continue
            selected.append(text)
            total += len(text)
            if total >= max_chars:
                break
        if not selected:
            selected = [text for _score, _index, text in scored[:8]]
        return "\n\n".join(selected)[:max_chars]


def merge_datasheet_repair(local: dict, repair: dict) -> dict:
    merged = deepcopy(local)
    if not isinstance(repair, dict):
        return merged
    repair_pins = clean_repair_pins(((repair.get("pinout") or {}).get("pins") if isinstance(repair.get("pinout"), dict) else []))
    local_pins = ((local.get("pinout") or {}).get("pins") or [])
    if repair_pinout_is_stronger(repair_pins, local_pins):
        pinout = dict(local.get("pinout") or {})
        pinout["pins"] = repair_pins
        merged["pinout"] = pinout

    merged["facts"] = merge_repair_facts(local.get("facts") or [], repair.get("facts") or [])
    for key in ("componentName", "componentType", "summary"):
        if not merged.get(key) and repair.get(key):
            merged[key] = str(repair.get(key)).strip()
    merged["confidence"] = max(optional_float(local.get("confidence")) or 0.0, min(optional_float(repair.get("confidence")) or 0.0, 0.97))
    merged["extractorVersion"] = DATASHEET_INTELLIGENCE_VERSION
    return merged


def clean_repair_pins(raw_pins) -> list[dict]:
    pins: list[dict] = []
    seen = set()
    if not isinstance(raw_pins, list):
        return pins
    for raw in raw_pins:
        if not isinstance(raw, dict):
            continue
        pin = optional_int(raw.get("pin"))
        label = re.sub(r"\s+", " ", str(raw.get("label") or raw.get("function") or "")).strip()
        function = re.sub(r"\s+", " ", str(raw.get("function") or label)).strip()
        if not pin or pin <= 0 or pin in seen or not label or len(label) > 40:
            continue
        seen.add(pin)
        pins.append({
            "pin": pin,
            "label": label[:40],
            "function": function[:80],
            "page": optional_int(raw.get("page")),
            "evidence": re.sub(r"\s+", " ", str(raw.get("evidence") or "")).strip()[:240],
        })
    return sorted(pins, key=lambda item: item["pin"])


def repair_pinout_is_stronger(repair_pins: list[dict], local_pins: list[dict]) -> bool:
    if len(repair_pins) < 3:
        return False
    if len(local_pins) == 0:
        return True
    if len(repair_pins) > len(local_pins):
        return True
    return pinout_has_gaps({"pinout": {"pins": local_pins}}) and not pinout_has_gaps({"pinout": {"pins": repair_pins}})


def pinout_has_gaps(intelligence: dict) -> bool:
    pins = (intelligence.get("pinout") or {}).get("pins") or []
    if len(pins) < 4:
        return False
    numbers = sorted(optional_int(pin.get("pin")) for pin in pins if optional_int(pin.get("pin")) is not None)
    if not numbers:
        return False
    return numbers != list(range(numbers[0], numbers[-1] + 1))


def merge_repair_facts(local_facts: list[dict], repair_facts) -> list[dict]:
    result = [deepcopy(fact) for fact in local_facts]
    seen = {
        (
            str(fact.get("type") or "").lower(),
            str(fact.get("label") or "").lower(),
            str(fact.get("value") or "").lower(),
            str(fact.get("unit") or "").lower(),
        )
        for fact in result
    }
    if not isinstance(repair_facts, list):
        return result
    for raw in repair_facts:
        if not isinstance(raw, dict):
            continue
        fact_type = str(raw.get("type") or "").strip().lower()
        label = re.sub(r"\s+", " ", str(raw.get("label") or "")).strip()
        value = re.sub(r"\s+", " ", str(raw.get("value") or "")).strip()
        unit = re.sub(r"\s+", " ", str(raw.get("unit") or "")).strip()
        if fact_type not in {"voltage", "current", "package", "warning", "absolute_maximum"} or not label or not value:
            continue
        key = (fact_type, label.lower(), value.lower(), unit.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "type": fact_type,
            "label": label[:80],
            "value": value[:180],
            "unit": unit[:20],
            "page": optional_int(raw.get("page")),
            "evidence": re.sub(r"\s+", " ", str(raw.get("evidence") or "")).strip()[:320],
            "confidence": min(max(optional_float(raw.get("confidence")) or 0.75, 0.0), 0.95),
        })
        if len(result) >= 24:
            break
    return result


def optional_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
