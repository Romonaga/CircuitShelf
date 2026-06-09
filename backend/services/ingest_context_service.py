import os
import re

from backend.ingestion.chunking_util import ChunkingUtils
from backend.services.ingestion_ai_review_service import IngestionAiReviewService
from backend.services.state_manager import StateManager
from backend.ingestion.tokenize_util import TokenUtils


class IngestContextService:
    def __init__(
        self,
        *,
        config,
        trace_logger,
        state,
        vector_store,
        ai_provider_store,
        openai_assist_service,
        query_local_llm,
        local_model_name: str | None,
        training_dir: str,
    ):
        self.config = config
        self.trace_logger = trace_logger
        self.state = state
        self.vector_store = vector_store
        self.training_dir = training_dir
        self.ai_review_service = IngestionAiReviewService(
            config=config,
            trace_logger=trace_logger,
            ai_provider_store=ai_provider_store,
            openai_assist_service=openai_assist_service,
            query_local_llm=query_local_llm,
            local_model_name=local_model_name,
        )

    def source_ingest_scope(self, source: str) -> dict:
        scope = self.vector_store.ingest_scope_overrides([source]).get(source)
        if not scope:
            scope = self.vector_store.document_scopes_for_sources([source]).get(source)
        is_global = bool(scope.get("is_global", True)) if scope else True
        return {
            "is_global": is_global,
            "entity_id": None if is_global else scope.get("entity_id"),
            "created_by_user_id": scope.get("created_by_user_id") if scope else None,
        }

    def ingested_document_payload(self, target_state, rel_path: str) -> tuple[list[str], list[dict]]:
        chunks: list[str] = []
        metadata: list[dict] = []
        seen_image_ids = set()
        for chunk, source, meta in zip(
            target_state.get_chunks(),
            target_state.get_sources(),
            target_state.get_metadata(),
        ):
            meta = meta or {}
            if self.vector_store.rel_path_for_source(source, meta) != rel_path:
                continue
            text = str(chunk or "").strip()
            if not text:
                continue
            chunks.append(text)
            metadata.append({**meta, "source": rel_path, "parent_source": rel_path})
            image_id = meta.get("source_image_id")
            if image_id:
                seen_image_ids.add(str(image_id))

        for image_id, text in target_state.get_image_page_text().items():
            if not text or str(image_id) in seen_image_ids:
                continue
            if not self.source_matches_training_file(image_id, rel_path):
                continue
            chunks.append(str(text).strip())
            metadata.append({
                "source": rel_path,
                "parent_source": rel_path,
                "page": self._page_number_from_image_id(image_id),
                "source_image_id": image_id,
                "is_ocr": True,
            })
        return chunks, metadata

    def sample_ingested_text(self, target_state, rel_path: str, max_chars: int = 6000) -> str:
        chunks, _metadata = self.ingested_document_payload(target_state, rel_path)
        samples: list[str] = []
        total = 0
        for text in chunks:
            samples.append(text)
            total += len(text)
            if total >= max_chars:
                break
        return "\n\n".join(samples)[:max_chars]

    def build_document_intelligence_for_ingest(self, source: str, ingested_state, document_intelligence_service):
        chunks, metadata = self.ingested_document_payload(ingested_state, source)
        if not chunks:
            return None
        return document_intelligence_service.get_or_build(source, chunks, metadata)

    def maybe_review_ingestion_with_openai(
        self,
        source: str,
        ingested_state,
        document_stats: dict | None,
        *,
        intelligence: dict | None = None,
        progress_callback=None,
    ):
        scope = self.source_ingest_scope(source)
        stats = (document_stats or {}).get(source, {})
        result = self.ai_review_service.review(
            source_path=source,
            is_global=bool(scope["is_global"]),
            entity_id=scope.get("entity_id"),
            user_id=scope.get("created_by_user_id"),
            stats=stats,
            sample_text=self.sample_ingested_text(ingested_state, source),
            intelligence=intelligence,
            openai_enabled=bool(self.config.get("INGEST_OPENAI_ASSIST_ENABLED", False)),
            progress_callback=progress_callback,
        )
        if result:
            self.trace_logger.debug(
                f"🤖 Ingestion AI review stored for {source} "
                f"provider={result.get('provider')} paid_by={result.get('paidBy')} "
                f"cost=${float(result.get('estimatedCost') or 0):.6f}."
            )
        return result

    @staticmethod
    def _page_number_from_image_id(image_id) -> int | None:
        match = re.search(r"_page(\d+)(?:_|$)", str(image_id or ""), re.IGNORECASE)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def build_ingest_context(self):
        ingest_state = StateManager(use_lock=True, cache_capacity=0, trace_logger=self.trace_logger)
        ingest_token_utils = TokenUtils(state=ingest_state, trace_logger=self.trace_logger)
        ingest_chunker = ChunkingUtils(
            state=ingest_state,
            token_utils=ingest_token_utils,
            config=self.config,
            trace_logger=self.trace_logger,
        )
        return ingest_state, ingest_token_utils, ingest_chunker

    def source_matches_training_file(self, candidate, rel_path: str) -> bool:
        if not candidate:
            return False

        candidate = os.path.normpath(str(candidate))
        rel_path = os.path.normpath(rel_path)
        full_path = os.path.normpath(os.path.join(self.training_dir, rel_path))
        base_name = os.path.basename(rel_path)
        candidate_base = os.path.basename(candidate)

        return (
            candidate == rel_path
            or candidate == full_path
            or candidate_base == base_name
            or candidate_base.startswith(f"{base_name}_page")
            or candidate_base.startswith(f"{base_name}_textbox")
        )

    def prune_training_files_from_state(self, rel_paths) -> None:
        if not rel_paths:
            return

        rel_paths = set(rel_paths)

        def matches_any(candidate):
            return any(self.source_matches_training_file(candidate, rel_path) for rel_path in rel_paths)

        kept_chunks, kept_sources, kept_metadata = [], [], []
        kept_embeddings = []
        embeddings = self.state.get_embeddings()
        removed_chunks = 0
        for idx, (chunk, source, meta) in enumerate(
            zip(self.state.get_chunks(), self.state.get_sources(), self.state.get_metadata())
        ):
            meta = meta or {}
            candidates = [
                source,
                meta.get("source"),
                meta.get("parent_source"),
                meta.get("source_image_id"),
            ]
            if any(matches_any(candidate) for candidate in candidates):
                removed_chunks += 1
                continue
            kept_chunks.append(chunk)
            kept_sources.append(source)
            kept_metadata.append(meta)
            if idx < len(embeddings):
                kept_embeddings.append(embeddings[idx])

        image_store = {
            key: value
            for key, value in self.state.get_image_store().items()
            if not matches_any(key)
        }
        image_captions = {
            key: value
            for key, value in self.state.get_image_captions().items()
            if not matches_any(key)
        }
        image_page_text = {
            key: value
            for key, value in self.state.get_image_page_text().items()
            if not matches_any(key)
        }
        image_mime_types = {
            key: value
            for key, value in self.state.get_image_mime_types().items()
            if not matches_any(key)
        }
        image_id_list = [
            img_id for img_id in self.state.get_image_id_list()
            if not matches_any(img_id)
        ]

        self.state.replace_catalog(
            chunks=kept_chunks,
            sources=kept_sources,
            metadata=kept_metadata,
            embeddings=kept_embeddings,
            image_store=image_store,
            image_captions=image_captions,
            image_page_text=image_page_text,
            image_mime_types=image_mime_types,
            image_id_list=image_id_list,
        )

        self.trace_logger.info(
            f"🧹 Pruned {removed_chunks} chunks and removed OCR/image state for "
            f"{len(rel_paths)} changed/removed training files."
        )
