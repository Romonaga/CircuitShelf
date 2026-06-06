from dataclasses import dataclass

from sentence_transformers import SentenceTransformer

import backend.services.bench_tools as bench_tools
from backend.services.app_runtime_helpers import conversation_title_from_question, sanitize_for_json
from backend.services.document_intelligence_service import DocumentIntelligenceService
from backend.services.document_management_service import DocumentManagementService
from backend.ingestion import IngestionPipeline
from backend.services.image_retrieval_service import ImageRetrievalService
from backend.services.image_state_service import ImageStateService
from backend.services.incremental_ingest_service import IncrementalIngestService
from backend.services.index_lifecycle_service import IndexLifecycleService
from backend.services.ingest_context_service import IngestContextService
from backend.services.ingest_housekeeping import IngestHousekeepingService
from backend.services.ingest_progress import IngestProgressTracker, utc_now, utc_now_iso
from backend.services.ingest_stats import (
    collect_document_ingest_stats,
    count_state_chunks_by_document,
    count_state_images_by_document,
    file_changes_payload,
    summarize_document_ingest_stats,
)
from backend.services.ollama_chat_client import OllamaChatClient
from backend.services.prompt_service import PromptService
from backend.services.rag_service import RagService
from backend.services.retrieval_service import QueryPreprocessor, RuntimeChunkMapper
from backend.services.runtime_status_service import (
    RuntimeStatusReporter,
    effective_embedding_batch_size as runtime_effective_embedding_batch_size,
    effective_rerank_batch_size as runtime_effective_rerank_batch_size,
)
from backend.services.model_runtime import resolve_model_device
from backend.services.source_metadata import (
    build_source_payload,
    display_source_name,
    document_source_from_metadata,
    image_asset_belongs_to_document,
    normalize_sources_for_api,
    source_image_id_from_metadata,
)
from backend.ingestion.chunking_util import ChunkingUtils
from backend.services.circuit_build_cards import RECOVERY_SYSTEM_PROMPT, build_recovery_prompt, parse_recovered_build_card
from backend.ingestion.manifest import IngestManifest
from backend.ingestion.worker_sizing import (
    detected_cpu_count,
    document_worker_count,
    ocr_worker_count,
    persist_worker_count,
    reserved_core_count,
    usable_core_count,
)
from backend.services.inventory_import import parse_inventory_import
from backend.services.log_retention import cleanup_old_logs
from backend.services.log_tail import tail_recent_trace_logs
from backend.ingestion.ocr_utils import run_ocr
from backend.ingestion.pinout_extractor import extract_pinout_map
from backend.services.reranker import Reranker
from backend.services.response_finalizer import RESPONSE_FINALIZER_SYSTEM_PROMPT
from backend.ingestion.tokenize_util import TokenUtils
from backend.services.system_init import SystemInit


@dataclass
class CircuitShelfRuntime:
    config: object
    trace_logger: object
    state: object
    database: object
    stores: object
    runtime_settings: object
    trace_log_helper: object
    ingest_status_callback: object | None = None
    ingest_status_provider: object | None = None
    enable_inprocess_ingest_watch: bool = False

    def __post_init__(self):
        self._load_config_values()
        self._build_processing_services()
        self._build_ingest_services()
        self._build_query_services()
        self._build_api_helpers()

    def _load_config_values(self):
        config = self.config
        self.post_timeout = config.get("POST_TIMEOUT", 60)
        self.react_dist_dir = config.get("REACT_DIST_DIR", "frontend/dist")
        self.query_retries = config.get("QUERY_RETRIES", 3)
        self.query_retry_delay = config.get("QUERY_RETRY_DELAY", 5)
        self.doc_ext = config.get("DOC_EXT")
        self.pdf_ext = config.get("PDF_EXT")
        self.md_ext = config.get("MD_EXT")
        self.prompt_dir = config.get("PROMPT_DIR", "prompts")
        self.training_dir = config.get("TRAINING_DIR", "training")
        self.trace_log_file = config.get("TRACE_LOG_FILE", "logs/trace.log")
        self.log_retention_days = config.get("LOG_RETENTION_DAYS", 7)
        self.tesseract_temp_max_age_seconds = 3600
        self.embed_model_name = config.get("EMBED_MODEL_NAME")
        self.llm_model_name = config.get("LLM_MODEL_NAME")
        self.ollama_api_url = config.get("OLLAMA_API_URL")
        self.llm_temperature = config.get("LLM_TEMPERATURE", 0.2)
        self.llm_num_predict = config.get("LLM_NUM_PREDICT", 3072)
        self.llm_num_ctx = config.get("LLM_NUM_CTX")
        self.local_llm_max_concurrent = config.get("LOCAL_LLM_MAX_CONCURRENT", 1)
        self.local_llm_queue_timeout_seconds = config.get("LOCAL_LLM_QUEUE_TIMEOUT_SECONDS", 300)
        self.ollama_keep_alive = config.get("OLLAMA_KEEP_ALIVE", "30s")
        self.cross_encoder_model = config.get("CROSS_ENCODER_MODEL")
        self.model_device = resolve_model_device(config)
        self.llm_model_options = config.get("LLM_MODEL_OPTIONS")
        self.max_chat_history_turns = config.get("MAX_CHAT_HISTORY_TURNS", 5)
        self.max_chat_history_chars = config.get("MAX_CHAT_HISTORY_CHARS", 2000)
        self.banned_phrases = config.get("PROMPT_SECURITY", {}).get("BANNED_PHRASES", [])
        self.rag_chat_system_prompt = config.get(
            "RAG_CHAT_SYSTEM_PROMPT",
            (
                "You are CircuitShelf's retrieval-grounded electronics assistant. "
                "Use the provided retrieved context as the source of truth. If the context "
                "does not contain enough information, say what is missing instead of making "
                "up facts. Preserve useful prior chat context for follow-up questions. "
                "A CircuitShelf build card is an app-rendered bench card with parts, power notes, "
                "pin-by-pin wiring, checks, warnings, and source notes. If the user asks for a "
                "build card, treat that as a request for practical build-ready guidance; do not "
                "say you do not know what a build card is. "
                "When the user asks how to build or wire something, give practical pin-by-pin "
                "steps, power and ground details, component values when supported by context, "
                "and safety cautions."
            ),
        )
        self.response_finalizer_enabled = bool(config.get("RESPONSE_FINALIZER_ENABLED", True))
        self.response_finalizer_mode = config.get("RESPONSE_FINALIZER_MODE", "always")
        self.response_finalizer_min_confidence = float(config.get("RESPONSE_FINALIZER_MIN_CONFIDENCE", 0.80))
        self.response_finalizer_max_context_chars = int(config.get("RESPONSE_FINALIZER_MAX_CONTEXT_CHARS", 7000))
        self.rerank_profiles = config.get("RERANK_PROFILES")
        config.validate_rerank_profiles(self.rerank_profiles)

    def _build_processing_services(self):
        stores = self.stores
        self.token_utils = TokenUtils(state=self.state, trace_logger=self.trace_logger)
        self.chunker = ChunkingUtils(
            state=self.state,
            token_utils=self.token_utils,
            config=self.config,
            trace_logger=self.trace_logger,
        )
        self.trace_logger.info(f"🧠 Loading embedding and reranker models on device: {self.model_device}")
        self.embedder = SentenceTransformer(self.embed_model_name, device=self.model_device)
        self.reranker_engine = Reranker(
            self.config,
            self.state,
            self.chunker,
            self.trace_logger,
            device=self.model_device,
            batch_size_resolver=self.effective_rerank_batch_size,
        )
        self.runtime_settings.register_callback(
            "RERANK_PROFILES",
            lambda value: setattr(self.reranker_engine, "rerank_profiles", value),
        )
        self.ingest_progress = IngestProgressTracker(
            config=self.config,
            status_callback=self.ingest_status_callback,
        )
        self.index_status = self.ingest_progress.status
        self.image_retrieval_service = ImageRetrievalService(
            state=self.state,
            embedder=self.embedder,
            image_store=stores.image_store,
        )
        self.image_state_service = ImageStateService(
            state=self.state,
            vector_store=stores.vector_store,
            image_store=stores.image_store,
            chunker=self.chunker,
            embedder=self.embedder,
            config=self.config,
            trace_logger=self.trace_logger,
            embedding_model_name=self.embed_model_name,
            effective_embedding_batch_size=self.effective_embedding_batch_size,
            update_index_detail=self.ingest_progress.update_detail,
            update_index_progress=self.ingest_progress.update_progress,
        )
        self.ingest_housekeeping = IngestHousekeepingService(
            config=self.config,
            trace_logger=self.trace_logger,
            cleanup_old_logs=cleanup_old_logs,
            trace_log_file=self.trace_log_file,
            active_trace_log_file=self.trace_log_helper.current_file,
            log_retention_days=self.log_retention_days,
            tesseract_temp_max_age_seconds=self.tesseract_temp_max_age_seconds,
        )
        self.ingest_context_service = IngestContextService(
            config=self.config,
            trace_logger=self.trace_logger,
            state=self.state,
            vector_store=stores.vector_store,
            ai_provider_store=stores.ai_provider_store,
            openai_assist_service=stores.openai_assist_service,
            query_local_llm=self.query_ollama_chat_with_retry,
            local_model_name=self.llm_model_name,
            training_dir=self.training_dir,
        )
        self.ingestion_pipeline = IngestionPipeline(
            config=self.config,
            trace_logger=self.trace_logger,
            run_ocr=run_ocr,
            detected_cpu_count=detected_cpu_count,
            reserved_core_count=reserved_core_count,
            usable_core_count=usable_core_count,
            document_worker_count=document_worker_count,
            ocr_worker_count=ocr_worker_count,
            current_document_workers=self.ingest_progress.current_document_workers,
            begin_document_worker=self.ingest_progress.begin_document_worker,
            finish_document_worker=self.ingest_progress.finish_document_worker,
            pdf_ext=self.pdf_ext,
        )

    def _build_ingest_services(self):
        stores = self.stores
        self.incremental_ingest_service = IncrementalIngestService(
            config=self.config,
            trace_logger=self.trace_logger,
            training_dir=self.training_dir,
            vector_store=stores.vector_store,
            embedder=self.embedder,
            build_ingest_manifest=self.build_ingest_manifest,
            build_ingest_context=self.ingest_context_service.build_ingest_context,
            process_file_by_type=self.ingestion_pipeline.process_file_by_type,
            load_documents_parallel=self.ingestion_pipeline.load_documents_parallel,
            prune_training_files_from_state=self.ingest_context_service.prune_training_files_from_state,
            persist_db_image_state=self.image_state_service.persist_db_image_state,
            maybe_review_ingestion_with_openai=self.ingest_context_service.maybe_review_ingestion_with_openai,
            collect_ingest_stats=collect_document_ingest_stats,
            count_ingest_chunks_by_document=count_state_chunks_by_document,
            count_ingest_images_by_document=count_state_images_by_document,
            summarize_document_ingest_stats=summarize_document_ingest_stats,
            image_asset_belongs_to_document=image_asset_belongs_to_document,
            detected_cpu_count=detected_cpu_count,
            reserved_core_count=reserved_core_count,
            usable_core_count=usable_core_count,
            document_worker_count=document_worker_count,
            persist_worker_count=persist_worker_count,
            begin_document_worker=self.ingest_progress.begin_document_worker,
            finish_document_worker=self.ingest_progress.finish_document_worker,
            update_index_progress=self.ingest_progress.update_progress,
            update_index_detail=self.ingest_progress.update_detail,
            index_status=self.index_status,
            effective_embedding_batch_size=self.effective_embedding_batch_size,
        )
        self.index_lifecycle_service = IndexLifecycleService(
            config=self.config,
            trace_logger=self.trace_logger,
            state=self.state,
            vector_store=stores.vector_store,
            image_store=stores.image_store,
            performance_store=stores.performance_store,
            training_dir=self.training_dir,
            build_ingest_manifest=self.build_ingest_manifest,
            run_incremental_ingest=self.incremental_ingest_service.run_incremental_ingest,
            file_changes_payload=file_changes_payload,
            set_index_status=self.ingest_progress.set_status,
            schedule_next_ingest_check=self.ingest_progress.schedule_next_check,
            seconds_until_next_ingest_check=self.ingest_progress.seconds_until_next_check,
            ingest_watch_interval_seconds=self.ingest_progress.watch_interval_seconds,
            index_status=self.index_status,
            ingest_progress=self.ingest_progress,
            run_index_housekeeping=self.ingest_housekeeping.run_index_housekeeping,
            load_db_image_state=self.image_state_service.load_db_image_state,
            backfill_missing_image_embeddings=self.image_state_service.backfill_missing_image_embeddings,
            system_log_build_info=SystemInit.log_build_info,
            utc_now=utc_now,
            utc_now_iso=utc_now_iso,
        )
        if self.enable_inprocess_ingest_watch:
            self.runtime_settings.register_callback(
                "INGEST_WATCH_ENABLED",
                self.index_lifecycle_service.apply_ingest_watch_enabled,
            )
            self.runtime_settings.register_callback(
                "INGEST_WATCH_INTERVAL_SECONDS",
                self.index_lifecycle_service.apply_ingest_watch_interval,
            )

    def _build_query_services(self):
        stores = self.stores
        self.document_intelligence_service = DocumentIntelligenceService(
            state=self.state,
            vector_store=stores.vector_store,
            intelligence_store=stores.intelligence_store,
            trace_logger=self.trace_logger,
            training_dir=self.training_dir,
            display_source_name=display_source_name,
            document_source_from_metadata=document_source_from_metadata,
            image_asset_belongs_to_document=image_asset_belongs_to_document,
            extract_page_number=self.ingestion_pipeline.extract_page_number,
            config=self.config,
            openai_assist_service=stores.openai_assist_service,
        )
        self.query_preprocessor = QueryPreprocessor(
            config=self.config,
            trace_logger=self.trace_logger,
            banned_phrases=self.banned_phrases,
        )
        self.runtime_chunk_mapper = RuntimeChunkMapper(
            state=self.state,
            vector_store=stores.vector_store,
            trace_logger=self.trace_logger,
        )
        self.prompt_service = PromptService(
            config=self.config,
            prompt_dir=self.prompt_dir,
            trace_logger=self.trace_logger,
            token_length=TokenUtils.tokenize_len,
        )
        self.ollama_chat_client = OllamaChatClient(
            config=self.config,
            trace_logger=self.trace_logger,
            api_url=self.ollama_api_url,
            default_system_prompt=self.rag_chat_system_prompt,
            default_temperature=self.llm_temperature,
            default_num_predict=self.llm_num_predict,
            default_num_ctx=self.llm_num_ctx,
            post_timeout=self.post_timeout,
            query_retries=self.query_retries,
            query_retry_delay=self.query_retry_delay,
            max_chat_history_turns=self.max_chat_history_turns,
            max_chat_history_chars=self.max_chat_history_chars,
            max_concurrent_requests=self.local_llm_max_concurrent,
            queue_timeout_seconds=self.local_llm_queue_timeout_seconds,
            keep_alive=self.ollama_keep_alive,
        )
        self.runtime_settings.register_callback(
            "LOCAL_LLM_MAX_CONCURRENT",
            lambda value: self.ollama_chat_client.configure_runtime(max_concurrent_requests=int(value or 1)),
        )
        self.runtime_settings.register_callback(
            "LOCAL_LLM_QUEUE_TIMEOUT_SECONDS",
            lambda value: self.ollama_chat_client.configure_runtime(queue_timeout_seconds=float(value or 0)),
        )
        self.runtime_settings.register_callback(
            "OLLAMA_KEEP_ALIVE",
            lambda value: self.ollama_chat_client.configure_runtime(keep_alive=value),
        )
        self.rag_service = RagService(
            state=self.state,
            trace_logger=self.trace_logger,
            embedder=self.embedder,
            vector_store=stores.vector_store,
            chunker=self.chunker,
            reranker_engine=self.reranker_engine,
            prompt_service=self.prompt_service,
            query_preprocessor=self.query_preprocessor,
            runtime_chunk_mapper=self.runtime_chunk_mapper,
            response_cache=stores.db_response_cache,
            query_log_store=stores.query_log_store,
            openai_assist_service=stores.openai_assist_service,
            document_intelligence_service=self.document_intelligence_service,
            image_retrieval_service=self.image_retrieval_service,
            build_source_payload=build_source_payload,
            query_llm=self.query_ollama_chat_with_retry,
            llm_model_options=self.llm_model_options,
            default_llm_model=self.llm_model_name,
            max_chat_history_turns=self.max_chat_history_turns,
            max_chat_history_chars=self.max_chat_history_chars,
            response_finalizer_system_prompt=RESPONSE_FINALIZER_SYSTEM_PROMPT,
            response_finalizer_enabled=self.response_finalizer_enabled,
            response_finalizer_mode=self.response_finalizer_mode,
            response_finalizer_min_confidence=self.response_finalizer_min_confidence,
            response_finalizer_max_context_chars=self.response_finalizer_max_context_chars,
        )
        self.runtime_status_reporter = RuntimeStatusReporter(
            config=self.config,
            state=self.state,
            vector_store=stores.vector_store,
            image_store=stores.image_store,
            response_cache=stores.db_response_cache,
            performance_store=stores.performance_store,
            database=self.database,
            embedding_model_name=self.embed_model_name,
            reranker_model_name=self.cross_encoder_model,
            llm_model_name=self.llm_model_name,
            model_device_name=self.model_device,
            detected_cpu_count_fn=detected_cpu_count,
            reserved_core_count_fn=reserved_core_count,
            usable_core_count_fn=usable_core_count,
            active_document_worker_count_fn=self.ingest_progress.active_document_worker_count,
            index_status=self.index_status,
            ingest_status_provider=self.ingest_status_provider,
            local_llm_status_provider=self.ollama_chat_client.status,
        )
        self.document_management_service = DocumentManagementService(
            vector_store=stores.vector_store,
            training_dir=self.training_dir,
            trace_logger=self.trace_logger,
            prune_training_files_from_state=self.ingest_context_service.prune_training_files_from_state,
        )

    def _build_api_helpers(self):
        self.bench_tools = bench_tools
        self.conversation_title_from_question = conversation_title_from_question
        self.normalize_sources_for_api = normalize_sources_for_api
        self.build_recovery_prompt = build_recovery_prompt
        self.parse_recovered_build_card = parse_recovered_build_card
        self.recovery_system_prompt = RECOVERY_SYSTEM_PROMPT
        self.image_asset_belongs_to_document = image_asset_belongs_to_document
        self.document_source_from_metadata = document_source_from_metadata
        self.source_image_id_from_metadata = source_image_id_from_metadata
        self.extract_pinout_map = extract_pinout_map
        self.display_source_name = display_source_name
        self.sanitize_for_json = sanitize_for_json
        self.tail_text_file = tail_recent_trace_logs
        self.parse_inventory_import = parse_inventory_import

    def supported_training_extensions(self):
        return {
            self.doc_ext,
            self.pdf_ext,
            self.md_ext,
            ".txt",
            *self.config.get("IMG_EXTENSIONS", []),
        }

    def build_ingest_manifest(self):
        return IngestManifest(
            manifest_path="",
            training_dir=self.training_dir,
            supported_extensions=self.supported_training_extensions(),
            recursive=self.config.get("TRAINING_RECURSIVE", True),
            excluded_dirs=self.config.get("TRAINING_EXCLUDE_DIRS", []),
            hash_files=self.config.get("INGEST_HASH_FILES", False),
        )

    def query_ollama_chat_with_retry(
        self,
        prompt,
        model_name,
        chat_history=None,
        retries=None,
        delay=None,
        system_prompt=None,
    ):
        return self.ollama_chat_client.chat_with_retry(
            prompt,
            model_name,
            chat_history=chat_history,
            retries=retries,
            delay=delay,
            system_prompt=system_prompt,
        )

    def image_asset_count_for_document(self, doc_source):
        return sum(
            1
            for image_id in self.state.get_image_store().keys()
            if image_asset_belongs_to_document(image_id, doc_source)
        )

    def effective_embedding_batch_size(self):
        return runtime_effective_embedding_batch_size(self.config)

    def effective_rerank_batch_size(self):
        return runtime_effective_rerank_batch_size(self.config)

    def session_timeout_seconds(self) -> int:
        return max(60, int(self.config.get("SESSION_TIMEOUT_SECONDS", self.config.get("SESSION_TTL_SECONDS", 28800))))

    def start_ingest_watcher(self):
        return self.index_lifecycle_service.start_ingest_watcher()

    def stop_ingest_watcher(self):
        return self.index_lifecycle_service.stop_ingest_watcher()

    def cleanup_stale_tesseract_temp_files(self):
        return self.ingest_housekeeping.cleanup_stale_tesseract_temp_files()

    def get_or_build_index(self):
        return self.index_lifecycle_service.get_or_build_index()
