import os
import re
from collections import OrderedDict
from typing import Callable

from datasheet_intelligence import build_datasheet_intelligence


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

    def rel_path(self, source: str | None) -> str:
        return self.vector_store.rel_path_for_source(source or "", {})

    def build_from_payload(self, doc_name: str, chunks: list[str], metadata: list[dict]) -> dict:
        return build_datasheet_intelligence(
            chunks,
            metadata,
            doc_name,
            self.display_source_name(doc_name),
        )

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

    @staticmethod
    def stored_is_usable(stored: dict | None) -> bool:
        if not stored:
            return False
        component_name = str(stored.get("componentName") or "").strip().upper()
        if component_name in {"", "LOGIC", "INPUT", "OUTPUT", "COMMON", "ABSOLUTE", "MAXIMUM"}:
            return False
        return bool(stored.get("facts") or stored.get("pinout", {}).get("pins"))

    def get_or_build(self, doc_name: str, chunks: list[str] | None = None, metadata: list[dict] | None = None) -> dict:
        rel_path = self.rel_path(doc_name)
        stored = self.intelligence_store.get_for_source(rel_path)
        if self.stored_is_usable(stored):
            if not stored.get("pinout", {}).get("pins"):
                refreshed = self.build_from_payload(doc_name, chunks, metadata or []) if chunks is not None else self.build_for_document(doc_name)
                if refreshed.get("pinout", {}).get("pins"):
                    self.intelligence_store.upsert(rel_path, refreshed)
                    return refreshed
            return stored

        intelligence = self.build_from_payload(doc_name, chunks, metadata or []) if chunks is not None else self.build_for_document(doc_name)
        stored = self.intelligence_store.replace_for_source(rel_path, intelligence)
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
