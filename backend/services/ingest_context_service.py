import os

from backend.ingestion.chunking_util import ChunkingUtils
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
        openai_assist_service,
        training_dir: str,
    ):
        self.config = config
        self.trace_logger = trace_logger
        self.state = state
        self.vector_store = vector_store
        self.openai_assist_service = openai_assist_service
        self.training_dir = training_dir

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

    def sample_ingested_text(self, target_state, rel_path: str, max_chars: int = 6000) -> str:
        samples = []
        for chunk, source, meta in zip(
            target_state.get_chunks(),
            target_state.get_sources(),
            target_state.get_metadata(),
        ):
            meta = meta or {}
            if self.vector_store.rel_path_for_source(source, meta) != rel_path:
                continue
            text = str(chunk or "").strip()
            if text:
                samples.append(text)
            if sum(len(item) for item in samples) >= max_chars:
                break
        return "\n\n".join(samples)[:max_chars]

    def maybe_review_ingestion_with_openai(self, source: str, ingested_state, document_stats: dict | None):
        if not self.config.get("INGEST_OPENAI_ASSIST_ENABLED", False):
            return None
        scope = self.source_ingest_scope(source)
        stats = (document_stats or {}).get(source, {})
        result = self.openai_assist_service.review_ingestion(
            source_path=source,
            is_global=bool(scope["is_global"]),
            entity_id=scope.get("entity_id"),
            user_id=scope.get("created_by_user_id"),
            stats=stats,
            sample_text=self.sample_ingested_text(ingested_state, source),
            enabled=True,
        )
        if result:
            self.trace_logger.debug(
                f"🤖 OpenAI ingestion review stored for {source} "
                f"using {result.get('paidBy')} billing (${float(result.get('estimatedCost') or 0):.6f})."
            )
        return result

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
