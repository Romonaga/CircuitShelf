from dataclasses import dataclass

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
from backend.services.gpu_work_queue import (
    GpuQueuedEmbedder,
    LocalGpuWorkCoordinator,
    detect_local_gpu_count,
    resolve_local_gpu_cuda_slots,
    resolve_local_gpu_llm_slots,
)
from backend.services.model_runtime import LazySentenceTransformer, release_accelerator_memory, resolve_model_device
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
from backend.ingestion.ocr_engines import ocr_uses_local_gpu, run_selected_ocr
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
    lazy_gpu_models: bool = False

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
        self.local_gpu_queue_timeout_seconds = config.get("LOCAL_GPU_QUEUE_TIMEOUT_SECONDS", 300)
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
        self.local_gpu_priority = 50 if self.lazy_gpu_models else 10
        self.local_gpu_owner = "ingest" if self.lazy_gpu_models else "web"
        self.detected_local_gpus = detect_local_gpu_count()
        self.local_gpu_llm_slots = resolve_local_gpu_llm_slots(self.config, detected_gpus=self.detected_local_gpus)
        self.local_gpu_cuda_slots = resolve_local_gpu_cuda_slots(self.config, detected_gpus=self.detected_local_gpus)
        self.local_gpu_coordinator = LocalGpuWorkCoordinator(
            database=self.database,
            logger=self.trace_logger,
            llm_slot_count=self.local_gpu_llm_slots,
            cuda_slot_count=self.local_gpu_cuda_slots,
            detected_gpu_count=self.detected_local_gpus,
            queue_timeout_seconds=self.local_gpu_queue_timeout_seconds,
        )
        self.runtime_settings.register_refresh_callback(
            {
                "LOCAL_GPU_LLM_SLOTS",
                "LOCAL_GPU_CUDA_SLOTS",
                "LOCAL_GPU_QUEUE_TIMEOUT_SECONDS",
            },
            lambda _key, _value: self.apply_gpu_runtime_settings(),
        )
        if self.lazy_gpu_models:
            self.trace_logger.info(f"🧠 Ingest runtime will cold-load GPU models on demand: {self.model_device}")
            raw_embedder = LazySentenceTransformer(self.embed_model_name, device=self.model_device, logger=self.trace_logger)
        else:
            from sentence_transformers import SentenceTransformer

            self.trace_logger.info(f"🧠 Loading embedding and reranker models on device: {self.model_device}")
            raw_embedder = SentenceTransformer(self.embed_model_name, device=self.model_device)
        self.embedder = GpuQueuedEmbedder(
            raw_embedder,
            self.local_gpu_coordinator,
            priority=self.local_gpu_priority,
            owner=self.local_gpu_owner,
        )
        self.reranker_engine = Reranker(
            self.config,
            self.state,
            self.chunker,
            self.trace_logger,
            device=self.model_device,
            batch_size_resolver=self.effective_rerank_batch_size,
            lazy=self.lazy_gpu_models,
            gpu_coordinator=self.local_gpu_coordinator,
            gpu_priority=self.local_gpu_priority,
            gpu_owner=self.local_gpu_owner,
        )
        self.runtime_settings.register_callback("RERANK_PROFILES", lambda value: setattr(self.reranker_engine, "rerank_profiles", value))
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
            run_ocr=self.run_ingestion_ocr,
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

    def apply_gpu_runtime_settings(self):
        self.local_gpu_llm_slots = resolve_local_gpu_llm_slots(self.config, detected_gpus=self.detected_local_gpus)
        self.local_gpu_cuda_slots = resolve_local_gpu_cuda_slots(self.config, detected_gpus=self.detected_local_gpus)
        self.local_gpu_queue_timeout_seconds = float(self.config.get("LOCAL_GPU_QUEUE_TIMEOUT_SECONDS", 300) or 300)
        self.local_gpu_coordinator.configure(
            llm_slot_count=self.local_gpu_llm_slots,
            cuda_slot_count=self.local_gpu_cuda_slots,
            queue_timeout_seconds=self.local_gpu_queue_timeout_seconds,
        )

    def apply_ollama_runtime_settings(self):
        self.ollama_chat_client.configure_runtime(
            api_url=self.config.get("OLLAMA_API_URL"),
            default_system_prompt=self.config.get("RAG_CHAT_SYSTEM_PROMPT"),
            default_temperature=self.config.get("LLM_TEMPERATURE", 0.2),
            default_num_predict=self.config.get("LLM_NUM_PREDICT", 3072),
            default_num_ctx=self.config.get("LLM_NUM_CTX"),
            post_timeout=self.config.get("POST_TIMEOUT", 60),
            query_retries=self.config.get("QUERY_RETRIES", 3),
            query_retry_delay=self.config.get("QUERY_RETRY_DELAY", 5),
            max_chat_history_turns=self.config.get("MAX_CHAT_HISTORY_TURNS", 5),
            max_chat_history_chars=self.config.get("MAX_CHAT_HISTORY_CHARS", 2000),
            max_concurrent_requests=self.config.get("LOCAL_LLM_MAX_CONCURRENT", 1),
            queue_timeout_seconds=self.config.get("LOCAL_LLM_QUEUE_TIMEOUT_SECONDS", 300),
            keep_alive=self.config.get("OLLAMA_KEEP_ALIVE", "30s"),
        )

    def apply_rag_runtime_settings(self):
        self.rag_service.configure_runtime(
            default_llm_model=self.config.get("LLM_MODEL_NAME"),
            llm_model_options=self.config.get("LLM_MODEL_OPTIONS"),
            max_chat_history_turns=self.config.get("MAX_CHAT_HISTORY_TURNS", 5),
            max_chat_history_chars=self.config.get("MAX_CHAT_HISTORY_CHARS", 2000),
            response_finalizer_enabled=self.config.get("RESPONSE_FINALIZER_ENABLED", True),
            response_finalizer_mode=self.config.get("RESPONSE_FINALIZER_MODE", "always"),
            response_finalizer_min_confidence=self.config.get("RESPONSE_FINALIZER_MIN_CONFIDENCE", 0.80),
            response_finalizer_max_context_chars=self.config.get("RESPONSE_FINALIZER_MAX_CONTEXT_CHARS", 7000),
        )

    def run_ingestion_ocr(self, image, ocr_config):
        if not ocr_uses_local_gpu(ocr_config):
            return run_selected_ocr(image, ocr_config)

        width, height = image.size
        with self.local_gpu_coordinator.lease(
            task_type="paddleocr",
            resource_class="cuda_batch",
            priority=self.local_gpu_priority,
            owner=self.local_gpu_owner,
            details={
                "engine": "paddleocr",
                "device": "gpu",
                "width": width,
                "height": height,
            },
        ):
            return run_selected_ocr(image, ocr_config)

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
            gpu_coordinator=self.local_gpu_coordinator,
            gpu_priority=5,
            gpu_owner="web",
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
        self.runtime_settings.register_refresh_callback(
            {
                "LLM_MODEL_NAME",
                "OLLAMA_API_URL",
                "POST_TIMEOUT",
                "QUERY_RETRIES",
                "QUERY_RETRY_DELAY",
                "RAG_CHAT_SYSTEM_PROMPT",
                "LLM_TEMPERATURE",
                "LLM_NUM_PREDICT",
                "LLM_NUM_CTX",
                "MAX_CHAT_HISTORY_TURNS",
                "MAX_CHAT_HISTORY_CHARS",
                "LOCAL_LLM_MAX_CONCURRENT",
                "LOCAL_LLM_QUEUE_TIMEOUT_SECONDS",
                "OLLAMA_KEEP_ALIVE",
            },
            lambda _key, _value: self.apply_ollama_runtime_settings(),
        )
        self.runtime_settings.register_refresh_callback(
            {
                "LLM_MODEL_NAME",
                "LLM_MODEL_OPTIONS",
                "MAX_CHAT_HISTORY_TURNS",
                "MAX_CHAT_HISTORY_CHARS",
                "RESPONSE_FINALIZER_ENABLED",
                "RESPONSE_FINALIZER_MODE",
                "RESPONSE_FINALIZER_MIN_CONFIDENCE",
                "RESPONSE_FINALIZER_MAX_CONTEXT_CHARS",
            },
            lambda _key, _value: self.apply_rag_runtime_settings(),
        )
        self.runtime_settings.register_config_live_keys(
            {
                "CHUNK_SIZE",
                "CHUNK_OVERLAP",
                "CHUNKING_MODE",
                "MIN_TOKENS_PER_CHUNK",
                "MAX_TOKENS_PER_CHUNK",
                "MIN_CHUNK_QUALITY",
                "MIN_ACCEPTED_SCORE",
                "RERANK_FALLBACK_TOP_K",
                "RERANK_MAX_CONTEXT_CHUNKS",
                "EMBED_BATCH_SIZE",
                "EMBED_BATCH_AUTO",
                "RERANK_BATCH_SIZE",
                "RERANK_BATCH_AUTO",
                "TRAINING_RECURSIVE",
                "TRAINING_EXCLUDE_DIRS",
                "INGEST_HASH_FILES",
                "PDF_RENDER_VECTOR_PAGES",
                "PDF_RENDER_MAX_PAGES_PER_DOC",
                "PDF_RENDER_MIN_DRAWINGS",
                "PDF_RENDER_ZOOM",
                "PDF_RENDER_RASTER_PAGES",
                "PDF_RENDER_MIN_RASTER_COVERAGE",
                "PDF_RENDER_OCR_PAGES",
                "USE_MULTITHREAD_OCR",
                "INDEX_IMAGE_OCR_AS_TEXT",
                "OCR_ENGINE",
                "OCR_ENGINE_FALLBACK",
                "PADDLEOCR_DEVICE",
                "PADDLEOCR_LANG",
                "PADDLEOCR_ENGINE",
                "PADDLEOCR_PYTHON",
                "PADDLEOCR_TIMEOUT_SECONDS",
                "OCR_INDEX_TEXT_MIN_CHARS",
                "OCR_MIN_CONFIDENCE",
                "OCR_USE_TESSERACT_CONFIDENCE",
                "OCR_MIN_LENGTH",
                "OCR_MIN_MEANINGFUL_CHARS",
                "OCR_MIN_MEANINGFUL_WORDS",
                "OCR_MIN_UNIQUE_CHARS",
                "OCR_MIN_ALPHA_RATIO",
                "OCR_MAX_DIGIT_RATIO",
                "OCR_MAX_SYMBOL_RATIO",
                "OCR_MAX_SPACE_RATIO",
                "OCR_MAX_AVG_WORD_LEN",
                "OCR_LOW_CONTENT_MAX_SCORE",
                "OCR_SHORT_TEXT_MAX_SCORE",
                "OCR_TXT_DROP_SCORE",
                "LOG_RETENTION_DAYS",
                "STATUS_POLL_INTERVAL_SECONDS",
                "STATUS_POLL_ACTIVE_INTERVAL_SECONDS",
                "SESSION_TIMEOUT_SECONDS",
                "INGEST_LOCAL_AI_REVIEW_ENABLED",
                "INGEST_LOCAL_AI_MAX_PENDING",
                "INGEST_LOCAL_AI_ADMISSION_TIMEOUT_SECONDS",
                "INGEST_OPENAI_ASSIST_ENABLED",
                "DATASHEET_OPENAI_REPAIR_ENABLED",
                "PROMPT_TEMPLATE_GENERAL",
                "PROMPT_TEMPLATE_MATH",
            }
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
            gpu_model_residency_provider=self.gpu_model_residency,
            local_gpu_queue_provider=lambda: self.local_gpu_coordinator.status(recent_limit=30),
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
        gpu_priority=None,
        gpu_owner=None,
        gpu_resource_class="local_llm",
        gpu_admission_max_pending=None,
        gpu_admission_timeout_seconds=None,
        keep_alive=None,
    ):
        return self.ollama_chat_client.chat_with_retry(
            prompt,
            model_name,
            chat_history=chat_history,
            retries=retries,
            delay=delay,
            system_prompt=system_prompt,
            gpu_priority=gpu_priority,
            gpu_owner=gpu_owner,
            gpu_resource_class=gpu_resource_class,
            gpu_admission_max_pending=gpu_admission_max_pending,
            gpu_admission_timeout_seconds=gpu_admission_timeout_seconds,
            keep_alive=keep_alive,
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

    def gpu_model_residency(self):
        return {
            "lazy": bool(self.lazy_gpu_models),
            "gpuSlots": self.local_gpu_llm_slots,
            "llmGpuSlots": self.local_gpu_llm_slots,
            "cudaGpuSlots": self.local_gpu_cuda_slots,
            "detectedGpus": self.detected_local_gpus,
            "embeddingResident": bool(getattr(self.embedder, "resident", True)),
            "rerankerResident": bool(getattr(self.reranker_engine, "resident", True)),
        }

    def unload_idle_gpu_models(self) -> bool:
        released = False
        if self.lazy_gpu_models and hasattr(self.embedder, "unload"):
            released = bool(self.embedder.unload()) or released
        if self.lazy_gpu_models and hasattr(self.reranker_engine, "unload"):
            released = bool(self.reranker_engine.unload()) or released
        if released:
            release_accelerator_memory(self.trace_logger)
        return released
