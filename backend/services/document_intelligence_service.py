import os
import re
from collections import OrderedDict
from copy import deepcopy
from typing import Callable

from backend.ingestion.document_classifier import is_plausible_component
from datasheet_intelligence import DATASHEET_INTELLIGENCE_VERSION, build_datasheet_intelligence


class DocumentIntelligenceService:
    def __init__(
        self,
        *,
        state,
        vector_store,
        intelligence_store,
        trace_logger,
        training_dir: str,
        display_source_name: Callable[[str], str],
        document_source_from_metadata: Callable[[str, dict | None], str],
        image_asset_belongs_to_document: Callable[[str, str], bool],
        extract_page_number: Callable[[str], int | None],
        config: dict | None = None,
        openai_assist_service=None,
    ):
        self.state = state
        self.vector_store = vector_store
        self.intelligence_store = intelligence_store
        self.trace_logger = trace_logger
        self.training_dir = training_dir
        self.display_source_name = display_source_name
        self.document_source_from_metadata = document_source_from_metadata
        self.image_asset_belongs_to_document = image_asset_belongs_to_document
        self.extract_page_number = extract_page_number
        self.config = config or {}
        self.openai_assist_service = openai_assist_service

    def rel_path(self, source: str | None) -> str:
        return self.vector_store.rel_path_for_source(source or "", {})

    def build_from_payload(self, doc_name: str, chunks: list[str], metadata: list[dict]) -> dict:
        intelligence = build_datasheet_intelligence(
            chunks,
            metadata,
            doc_name,
            self.display_source_name(doc_name),
        )
        return self.repair_with_openai_if_needed(doc_name, chunks, metadata, intelligence)

    def build_for_document(self, doc_name: str) -> dict:
        doc_chunks = []
        doc_metadata = []
        chunks = self.state.get_chunks()
        metadata = self.state.get_metadata()
        sources = self.state.get_sources()

        for idx, source in enumerate(sources):
            meta = metadata[idx] if idx < len(metadata) else {}
            doc_source = self.document_source_from_metadata(source, meta)
            if doc_source != doc_name:
                continue
            doc_chunks.append(chunks[idx] if idx < len(chunks) else "")
            doc_metadata.append({**meta, "source": doc_name, "parent_source": doc_name})

        image_text = self.state.get_image_page_text()
        for image_id, text in image_text.items():
            if text and self.image_asset_belongs_to_document(image_id, doc_name):
                doc_chunks.append(text)
                doc_metadata.append({
                    "source": doc_name,
                    "parent_source": doc_name,
                    "page": self.extract_page_number(image_id),
                    "source_image_id": image_id,
                })

        return self.build_from_payload(doc_name, doc_chunks, doc_metadata)

    def repair_with_openai_if_needed(self, doc_name: str, chunks: list[str], metadata: list[dict], intelligence: dict) -> dict:
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
        confidence = _optional_float(intelligence.get("confidence")) or 0.0
        return pin_count == 0 or fact_count < 2 or confidence < 0.82 or _pinout_has_gaps(intelligence)

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

    @staticmethod
    def stored_is_usable(stored: dict | None) -> bool:
        if not stored:
            return False
        if int(stored.get("extractorVersion") or 0) < 2:
            return False
        document_type = str(stored.get("documentType") or "").strip()
        if document_type and document_type != "component_datasheet":
            return False
        component_name = str(stored.get("componentName") or "").strip().upper()
        if component_name in {"", "LOGIC", "INPUT", "OUTPUT", "COMMON", "ABSOLUTE", "MAXIMUM"}:
            return False
        if not is_plausible_component(component_name):
            return False
        return bool(stored.get("facts") or stored.get("pinout", {}).get("pins"))

    def get_or_build(self, doc_name: str, chunks: list[str] | None = None, metadata: list[dict] | None = None) -> dict:
        rel_path = self.rel_path(doc_name)
        stored = self.intelligence_store.get_for_source(rel_path)
        if self.stored_is_usable(stored):
            if not stored.get("pinout", {}).get("pins"):
                refreshed = self.build_from_payload(doc_name, chunks, metadata or []) if chunks is not None else self.build_for_document(doc_name)
                if refreshed.get("pinout", {}).get("pins"):
                    replaced = self.intelligence_store.replace_for_source(rel_path, refreshed)
                    return replaced or refreshed
            return stored

        intelligence = self.build_from_payload(doc_name, chunks, metadata or []) if chunks is not None else self.build_for_document(doc_name)
        if self.stored_is_usable(intelligence):
            stored = self.intelligence_store.replace_for_source(rel_path, intelligence)
            if stored:
                return stored
        else:
            self.trace_logger.debug(f"Skipping datasheet intelligence persistence for non-component document {doc_name}.")
            return intelligence
        if stored:
            return stored
        return intelligence

    def for_sources(self, source_payload: list[dict] | None) -> dict:
        result = {}
        for source in source_payload or []:
            source_name = source.get("source")
            if not source_name or source_name in result:
                continue
            try:
                result[source_name] = self.get_or_build(source_name)
            except Exception as exc:
                self.trace_logger.warning(f"Datasheet intelligence unavailable for {source_name}: {exc}")
        return result

    @staticmethod
    def question_component_terms(question: str | None) -> list[str]:
        terms = []
        for match in re.finditer(r"\b[A-Za-z]*\d[A-Za-z0-9-]{1,24}\b", question or ""):
            term = match.group(0).strip("-")
            if len(term) >= 3:
                terms.append(term)
        return list(OrderedDict.fromkeys(terms))

    def for_question_and_sources(self, question: str, source_payload: list[dict] | None) -> dict:
        result = {}
        for term in self.question_component_terms(question):
            for rel_path in self.vector_store.find_document_sources_by_term(term, limit=3):
                source_name = os.path.join(self.training_dir, rel_path)
                if source_name in result:
                    result[source_name]["questionMatch"] = True
                    continue
                try:
                    intelligence = self.get_or_build(source_name)
                    intelligence["questionMatch"] = True
                    result[source_name] = intelligence
                except Exception as exc:
                    self.trace_logger.warning(f"Datasheet intelligence lookup failed for term {term}: {exc}")
        result.update({key: value for key, value in self.for_sources(source_payload).items() if key not in result})
        return result


def merge_datasheet_repair(local: dict, repair: dict) -> dict:
    merged = deepcopy(local)
    if not isinstance(repair, dict):
        return merged
    repair_pins = _clean_repair_pins(((repair.get("pinout") or {}).get("pins") if isinstance(repair.get("pinout"), dict) else []))
    local_pins = ((local.get("pinout") or {}).get("pins") or [])
    if _repair_pinout_is_stronger(repair_pins, local_pins):
        pinout = dict(local.get("pinout") or {})
        pinout["pins"] = repair_pins
        merged["pinout"] = pinout

    merged["facts"] = _merge_repair_facts(local.get("facts") or [], repair.get("facts") or [])
    for key in ("componentName", "componentType", "summary"):
        if not merged.get(key) and repair.get(key):
            merged[key] = str(repair.get(key)).strip()
    merged["confidence"] = max(_optional_float(local.get("confidence")) or 0.0, min(_optional_float(repair.get("confidence")) or 0.0, 0.97))
    merged["extractorVersion"] = DATASHEET_INTELLIGENCE_VERSION
    return merged


def _clean_repair_pins(raw_pins) -> list[dict]:
    pins: list[dict] = []
    seen = set()
    if not isinstance(raw_pins, list):
        return pins
    for raw in raw_pins:
        if not isinstance(raw, dict):
            continue
        pin = _optional_int(raw.get("pin"))
        label = re.sub(r"\s+", " ", str(raw.get("label") or raw.get("function") or "")).strip()
        function = re.sub(r"\s+", " ", str(raw.get("function") or label)).strip()
        if not pin or pin <= 0 or pin in seen or not label or len(label) > 40:
            continue
        seen.add(pin)
        pins.append({
            "pin": pin,
            "label": label[:40],
            "function": function[:80],
            "page": _optional_int(raw.get("page")),
            "evidence": re.sub(r"\s+", " ", str(raw.get("evidence") or "")).strip()[:240],
        })
    return sorted(pins, key=lambda item: item["pin"])


def _repair_pinout_is_stronger(repair_pins: list[dict], local_pins: list[dict]) -> bool:
    if len(repair_pins) < 3:
        return False
    if len(local_pins) == 0:
        return True
    if len(repair_pins) > len(local_pins):
        return True
    return _pinout_has_gaps({"pinout": {"pins": local_pins}}) and not _pinout_has_gaps({"pinout": {"pins": repair_pins}})


def _pinout_has_gaps(intelligence: dict) -> bool:
    pins = (intelligence.get("pinout") or {}).get("pins") or []
    if len(pins) < 4:
        return False
    numbers = sorted(_optional_int(pin.get("pin")) for pin in pins if _optional_int(pin.get("pin")) is not None)
    if not numbers:
        return False
    return numbers != list(range(numbers[0], numbers[-1] + 1))


def _merge_repair_facts(local_facts: list[dict], repair_facts) -> list[dict]:
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
            "page": _optional_int(raw.get("page")),
            "evidence": re.sub(r"\s+", " ", str(raw.get("evidence") or "")).strip()[:320],
            "confidence": min(max(_optional_float(raw.get("confidence")) or 0.75, 0.0), 0.95),
        })
        if len(result) >= 24:
            break
    return result


def _optional_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
