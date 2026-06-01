# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 06:54:37 2025

@author: sueco, rew
"""


# ===  Imports, Logging, and Configuration ===

import os
import time
import threading
import bench_tools
from contextlib import asynccontextmanager
from sentence_transformers import SentenceTransformer



#internal
from backend.app_factory import create_circuitshelf_app, register_api_routes
from backend.api.dependencies import ApiDependencies
from backend.auth_dependencies import AuthDependencyService
from backend.bootstrap_environment import configure_nltk_and_tesseract
from backend.bootstrap_settings import bootstrap_database_settings
from backend.server import mount_react_app, start_app_server
from backend.store_container import create_store_container
from backend.services.app_runtime_helpers import (
    TraceLogHelper,
    conversation_title_from_question,
    sanitize_for_json,
)
from backend.services.ingest_stats import (
    collect_document_ingest_stats as collect_ingest_stats,
    count_state_chunks_by_document as count_ingest_chunks_by_document,
    count_state_images_by_document as count_ingest_images_by_document,
    file_changes_payload,
    summarize_document_ingest_stats,
)
from backend.services.ingest_context_service import IngestContextService
from backend.services.document_processing_service import DocumentProcessingService
from backend.services.incremental_ingest_service import IncrementalIngestService
from backend.services.ingest_housekeeping import IngestHousekeepingService
from backend.services.ingest_progress import IngestProgressTracker, utc_now, utc_now_iso
from backend.services.runtime_status_service import (
    RuntimeStatusReporter,
    effective_embedding_batch_size as runtime_effective_embedding_batch_size,
)
from backend.services.image_retrieval_service import ImageRetrievalService
from backend.services.image_state_service import ImageStateService
from backend.services.ollama_chat_client import OllamaChatClient
from backend.services.document_intelligence_service import DocumentIntelligenceService
from backend.services.document_management_service import DocumentManagementService
from backend.services.prompt_service import PromptService
from backend.services.rag_service import RagService
from backend.services.retrieval_service import QueryPreprocessor, RuntimeChunkMapper
from backend.services.source_metadata import (
    build_source_payload,
    display_source_name,
    document_source_from_metadata,
    image_asset_belongs_to_document,
    normalize_sources_for_api,
    source_image_id_from_metadata,
)
from state_manager import StateManager
from chunking_util import ChunkingUtils
from tokenize_util import TokenUtils
from system_init import SystemInit
from reranker_module import Reranker
from ocr_utils import run_ocr
from pdf_visuals import link_chunks_to_rendered_pages, render_pdf_visual_pages
from inventory_import import parse_inventory_import
from pinout_extractor import extract_pinout_map
from circuit_build_cards import (
    RECOVERY_SYSTEM_PROMPT,
    build_recovery_prompt,
    parse_recovered_build_card,
)
from response_finalizer import RESPONSE_FINALIZER_SYSTEM_PROMPT
from ingest_manifest import IngestManifest
from ingest_workers import detected_cpu_count, document_worker_count, ocr_worker_count, reserved_core_count, usable_core_count
from log_tail import tail_text_file
from log_retention import cleanup_old_logs
from db.connection import Database, database_url_from_config
from process_lock import ProcessLockError, acquire_process_lock
from settings_runtime import RuntimeSettingsManager

#Inits the logger as well as the configuraqtion system
config, trace_logger = SystemInit.load_config_and_logger()
state = StateManager(use_lock=True, cache_capacity=200, trace_logger=trace_logger)
database = Database(database_url_from_config(config), trace_logger)
if not database.configured:
    raise RuntimeError("DATABASE_URL is required. CircuitShelf is database-backed and no longer supports file-backed runtime state.")

settings_store, runtime_config_store = bootstrap_database_settings(
    database=database,
    config=config,
    trace_logger=trace_logger,
)
stores = create_store_container(database=database, config=config, trace_logger=trace_logger)
stores.assert_available()
user_store = stores.user_store
entity_store = stores.entity_store
password_policy_store = stores.password_policy_store
account_profile_store = stores.account_profile_store
ai_provider_store = stores.ai_provider_store
openai_assist_service = stores.openai_assist_service
openai_model_service = stores.openai_model_service
user_preferences_store = stores.user_preferences_store
query_log_store = stores.query_log_store
performance_store = stores.performance_store
conversation_store = stores.conversation_store
vector_store = stores.vector_store
image_store = stores.image_store
intelligence_store = stores.intelligence_store
assembly_plan_store = stores.assembly_plan_store
lab_inventory_store = stores.lab_inventory_store
project_finder_store = stores.project_finder_store
db_response_cache = stores.db_response_cache
trace_logger.info("🛠️ Configuration and logger successfully initialized.")

# === Decorators ===
def trace_timer(label):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            trace_logger.debug(f"⏱️ {label} took {duration:.2f} seconds")
            return result
        return wrapper
    return decorator

configure_nltk_and_tesseract(config=config, trace_logger=trace_logger)


# === System Configuration ===
POST_TIMEOUT = config.get("POST_TIMEOUT", 60)
REACT_DIST_DIR = config.get("REACT_DIST_DIR", "frontend/dist")
QUERY_RETRIES = config.get("QUERY_RETRIES", 3)
QUERY_RETRY_DELAY = config.get("QUERY_RETRY_DELAY", 5)

runtime_settings = RuntimeSettingsManager(config, globals(), trace_logger)

# === File Extensions ===
DOC_EXT = config.get("DOC_EXT")
PDF_EXT = config.get("PDF_EXT")
MD_EXT = config.get("MD_EXT")



# === Directory Info ===
PROMPT_DIR = config.get("PROMPT_DIR", "prompts")
TRAINING_DIR = config.get("TRAINING_DIR", "training")


# === Stats and logging ===
BUILD_INDEX_LOG_FILE = config.get("BUILD_INDEX_LOG_FILE")
TRACE_LOG_FILE = config.get("TRACE_LOG_FILE", "logs/trace.log")
LOG_RETENTION_DAYS = config.get("LOG_RETENTION_DAYS", 14)
TESSERACT_TEMP_MAX_AGE_SECONDS = 3600
trace_log_helper = TraceLogHelper(trace_logger=trace_logger, default_log_file=TRACE_LOG_FILE)


# === LLM model and training values ===
CHUNK_SIZE = config.get("CHUNK_SIZE")
CHUNK_OVERLAP = config.get("CHUNK_OVERLAP")
EMBED_MODEL_NAME = config.get("EMBED_MODEL_NAME")
LLM_MODEL_NAME = config.get("LLM_MODEL_NAME")
OLLAMA_API_URL = config.get("OLLAMA_API_URL")
LLM_TEMPERATURE = config.get("LLM_TEMPERATURE", 0.2)
LLM_NUM_PREDICT = config.get("LLM_NUM_PREDICT", 3072)
LLM_NUM_CTX = config.get("LLM_NUM_CTX")

CROSS_ENCODER_MODEL = config.get("CROSS_ENCODER_MODEL")
LLM_MODEL_OPTIONS = config.get("LLM_MODEL_OPTIONS")


# === Ollama chat and history settings ===
MAX_CHAT_HISTORY_TURNS = config.get("MAX_CHAT_HISTORY_TURNS", 5)
MAX_CHAT_HISTORY_CHARS = config.get("MAX_CHAT_HISTORY_CHARS", 2000)
BANNED_PHRASES = config.get("PROMPT_SECURITY", {}).get("BANNED_PHRASES", [])
RAG_CHAT_SYSTEM_PROMPT = config.get(
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
RESPONSE_FINALIZER_ENABLED = bool(config.get("RESPONSE_FINALIZER_ENABLED", True))
RESPONSE_FINALIZER_MODE = config.get("RESPONSE_FINALIZER_MODE", "always")
RESPONSE_FINALIZER_MIN_CONFIDENCE = float(config.get("RESPONSE_FINALIZER_MIN_CONFIDENCE", 0.80))
RESPONSE_FINALIZER_MAX_CONTEXT_CHARS = int(config.get("RESPONSE_FINALIZER_MAX_CONTEXT_CHARS", 7000))
# === Settings for Reranking ===
RERANK_PROFILES = config.get("RERANK_PROFILES")
EMBED_BATCH_SIZE = config.get("EMBED_BATCH_SIZE", 16)
SPECIAL_SECTION_PRIORITY = config.get("SPECIAL_SECTION_PRIORITY")



token_utils = TokenUtils(state=state, trace_logger=trace_logger)
chunker = ChunkingUtils(state=state, token_utils=token_utils, config=config, trace_logger=trace_logger)

#validat we have rerank profiles
config.validate_rerank_profiles(RERANK_PROFILES)


# === Initialize Globals ===

embedder = SentenceTransformer(EMBED_MODEL_NAME)
image_retrieval_service = ImageRetrievalService(
    state=state,
    embedder=embedder,
    image_store=image_store,
)

reranker_engine = Reranker(config, state, chunker, trace_logger)
runtime_settings.register_callback("RERANK_PROFILES", lambda value: setattr(reranker_engine, "rerank_profiles", value))
INDEX_JOB_LOCK = threading.Lock()
INGEST_WATCH_STOP = threading.Event()
INGEST_WATCH_RESCHEDULE = threading.Event()
INGEST_WATCH_THREAD = None
ingest_progress = IngestProgressTracker(config=config)
index_status = ingest_progress.status
set_index_status = ingest_progress.set_status
ingest_watch_interval_seconds = ingest_progress.watch_interval_seconds
schedule_next_ingest_check = ingest_progress.schedule_next_check
seconds_until_next_ingest_check = ingest_progress.seconds_until_next_check
update_index_progress = ingest_progress.update_progress
update_index_detail = ingest_progress.update_detail
begin_document_worker = ingest_progress.begin_document_worker
finish_document_worker = ingest_progress.finish_document_worker
current_document_workers = ingest_progress.current_document_workers
active_document_worker_count = ingest_progress.active_document_worker_count
image_state_service = ImageStateService(
    state=state,
    vector_store=vector_store,
    image_store=image_store,
    chunker=chunker,
    embedder=embedder,
    config=config,
    trace_logger=trace_logger,
    embedding_model_name=EMBED_MODEL_NAME,
    effective_embedding_batch_size=lambda: effective_embedding_batch_size(),
    update_index_detail=update_index_detail,
    update_index_progress=update_index_progress,
)
load_db_image_state = image_state_service.load_db_image_state
refresh_active_state_from_db = image_state_service.refresh_active_state_from_db
persist_db_image_state = image_state_service.persist_db_image_state
backfill_missing_image_embeddings = image_state_service.backfill_missing_image_embeddings
ingest_housekeeping = IngestHousekeepingService(
    config=config,
    trace_logger=trace_logger,
    cleanup_old_logs=cleanup_old_logs,
    trace_log_file=TRACE_LOG_FILE,
    active_trace_log_file=trace_log_helper.current_file,
    log_retention_days=LOG_RETENTION_DAYS,
    tesseract_temp_max_age_seconds=TESSERACT_TEMP_MAX_AGE_SECONDS,
)
cleanup_stale_tesseract_temp_files = ingest_housekeeping.cleanup_stale_tesseract_temp_files
cleanup_expired_trace_logs = ingest_housekeeping.cleanup_expired_trace_logs
run_index_housekeeping = ingest_housekeeping.run_index_housekeeping
ingest_context_service = IngestContextService(
    config=config,
    trace_logger=trace_logger,
    state=state,
    vector_store=vector_store,
    openai_assist_service=openai_assist_service,
    training_dir=TRAINING_DIR,
)
source_ingest_scope = ingest_context_service.source_ingest_scope
sample_ingested_text = ingest_context_service.sample_ingested_text
maybe_review_ingestion_with_openai = ingest_context_service.maybe_review_ingestion_with_openai
build_ingest_context = ingest_context_service.build_ingest_context
source_matches_training_file = ingest_context_service.source_matches_training_file
prune_training_files_from_state = ingest_context_service.prune_training_files_from_state
document_processing_service = DocumentProcessingService(
    config=config,
    trace_logger=trace_logger,
    state=state,
    chunker=chunker,
    token_utils=token_utils,
    run_ocr=run_ocr,
    render_pdf_visual_pages=render_pdf_visual_pages,
    link_chunks_to_rendered_pages=link_chunks_to_rendered_pages,
    detected_cpu_count=detected_cpu_count,
    reserved_core_count=reserved_core_count,
    usable_core_count=usable_core_count,
    document_worker_count=document_worker_count,
    ocr_worker_count=ocr_worker_count,
    current_document_workers=current_document_workers,
    begin_document_worker=begin_document_worker,
    finish_document_worker=finish_document_worker,
    pdf_ext=PDF_EXT,
)
ocr_image_bytes = document_processing_service.ocr_image_bytes
format_confidence = document_processing_service.format_confidence
image_bytes_to_png_bytes = document_processing_service.image_bytes_to_png_bytes
get_ocr_worker_count = document_processing_service.get_ocr_worker_count
ocr_pdf_image_job = document_processing_service.ocr_pdf_image_job
run_pdf_image_ocr_jobs = document_processing_service.run_pdf_image_ocr_jobs
should_report_page_progress = document_processing_service.should_report_page_progress
add_pdf_rendered_pages = document_processing_service.add_pdf_rendered_pages
load_pdf_text = document_processing_service.load_pdf_text
extract_images_from_docx_textboxes = document_processing_service.extract_images_from_docx_textboxes
extract_page_number = document_processing_service.extract_page_number
extract_first_number = document_processing_service.extract_first_number
process_docx_file = document_processing_service.process_docx_file
process_pdf_file = document_processing_service.process_pdf_file
process_text_file = document_processing_service.process_text_file
process_image_file = document_processing_service.process_image_file
process_file_by_type = document_processing_service.process_file_by_type
load_documents_parallel = document_processing_service.load_documents_parallel
incremental_ingest_service = IncrementalIngestService(
    config=config,
    trace_logger=trace_logger,
    training_dir=TRAINING_DIR,
    vector_store=vector_store,
    embedder=embedder,
    build_ingest_manifest=build_ingest_manifest,
    build_ingest_context=build_ingest_context,
    process_file_by_type=process_file_by_type,
    load_documents_parallel=load_documents_parallel,
    prune_training_files_from_state=prune_training_files_from_state,
    persist_db_image_state=persist_db_image_state,
    maybe_review_ingestion_with_openai=maybe_review_ingestion_with_openai,
    collect_ingest_stats=collect_ingest_stats,
    count_ingest_chunks_by_document=count_ingest_chunks_by_document,
    count_ingest_images_by_document=count_ingest_images_by_document,
    summarize_document_ingest_stats=summarize_document_ingest_stats,
    image_asset_belongs_to_document=image_asset_belongs_to_document,
    detected_cpu_count=detected_cpu_count,
    reserved_core_count=reserved_core_count,
    usable_core_count=usable_core_count,
    document_worker_count=document_worker_count,
    begin_document_worker=begin_document_worker,
    finish_document_worker=finish_document_worker,
    update_index_progress=update_index_progress,
    update_index_detail=update_index_detail,
    index_status=index_status,
    effective_embedding_batch_size=lambda: effective_embedding_batch_size(),
)
extract_document_for_incremental_ingest = incremental_ingest_service.extract_document_for_incremental_ingest
persist_incremental_document = incremental_ingest_service.persist_incremental_document
mark_source_ready_for_review = incremental_ingest_service.mark_source_ready_for_review
run_incremental_ingest = incremental_ingest_service.run_incremental_ingest
reindex_review_source = incremental_ingest_service.reindex_review_source


def supported_training_extensions():
    return {
        DOC_EXT,
        PDF_EXT,
        MD_EXT,
        ".txt",
        *config.get("IMG_EXTENSIONS", []),
    }


def build_ingest_manifest():
    return IngestManifest(
        manifest_path="",
        training_dir=TRAINING_DIR,
        supported_extensions=supported_training_extensions(),
        recursive=config.get("TRAINING_RECURSIVE", True),
        excluded_dirs=config.get("TRAINING_EXCLUDE_DIRS", []),
        hash_files=config.get("INGEST_HASH_FILES", False),
    )




def check_for_training_changes(reason="watch"):
    if not INDEX_JOB_LOCK.acquire(blocking=False):
        trace_logger.info(f"⏳ Index check skipped for {reason}; another index job is running.")
        performance_store.record_work_run(
            work_type="index_check",
            label="Index check skipped",
            trigger_reason=reason,
            status="skipped",
            details={"reason": "already_running"},
        )
        return set_index_status(lastResult="already_running")

    started_at = utc_now()
    work_status = "completed"
    work_label = "Index check"
    work_error = None
    work_details = {}
    set_index_status(
        running=True,
        stage="scanning",
        currentFiles=[],
        fileProgress={},
        processedFiles=0,
        totalFiles=0,
        lastStartedAt=utc_now_iso(),
        lastFinishedAt=None,
        lastReason=reason,
        lastError=None,
        lastResult="running",
        lastChanges=None,
        details={},
    )
    start_time = time.time()
    try:
        manifest = build_ingest_manifest()
        current_manifest = manifest.scan()
        previous_manifest = vector_store.load_document_records()
        changes = manifest.diff(previous_manifest, current_manifest)
        set_index_status(lastChanges=file_changes_payload(changes))
        if not changes.has_changes:
            trace_logger.info(f"✅ Index check found no training changes for {reason}.")
            work_label = "Index check: no changes"
            work_status = "skipped"
            work_details = file_changes_payload(changes)
            return set_index_status(
                running=False,
                stage="idle",
                currentFiles=[],
                fileProgress={},
                processedFiles=0,
                totalFiles=0,
                lastFinishedAt=utc_now_iso(),
                lastResult="no_changes",
                lastChanges=file_changes_payload(changes),
                details={},
            )

        set_index_status(
            stage="processing_documents",
            processedFiles=0,
            totalFiles=len(changes.changed_or_added),
            currentFiles=[],
            fileProgress={},
        )
        build_result, final_details = run_incremental_ingest(changes, current_manifest)
        duration = time.time() - start_time
        trace_logger.info(
            f"✅ Incremental index check completed in {duration:.2f} sec. "
            f"Chunks: {len(state.get_chunks())}, embeddings: {len(state.get_embeddings())}"
        )
        result = "updated"
        if build_result:
            result = f"review_ready {build_result.chunks} changed chunks"
            work_label = "Document ingest"
            work_details = final_details
        elif changes.removed and not changes.changed_or_added:
            result = f"ignored {len(changes.removed)} missing source files"
            work_label = "Index check: ignored missing sources"
            work_status = "skipped"
            work_details = final_details
        else:
            work_details = final_details
        return set_index_status(
            running=False,
            stage="idle",
            currentFiles=[],
            fileProgress={},
            processedFiles=len(changes.changed_or_added),
            totalFiles=len(changes.changed_or_added),
            lastFinishedAt=utc_now_iso(),
            lastResult=result,
            lastChanges=file_changes_payload(changes),
            details=final_details,
        )
    except Exception as exc:
        trace_logger.error(f"❌ Incremental index check failed for {reason}: {exc}")
        work_status = "failed"
        work_label = "Index check failed"
        work_error = str(exc)
        return set_index_status(
            running=False,
            stage="failed",
            currentFiles=[],
            fileProgress={},
            lastFinishedAt=utc_now_iso(),
            lastResult="failed",
            lastError=str(exc),
            details={},
        )
    finally:
        finished_at = utc_now()
        index_snapshot = ingest_progress.snapshot()
        detail_snapshot = dict(index_snapshot.get("details") or {})
        last_changes = index_snapshot.get("lastChanges")
        merged_details = {
            **(work_details or {}),
            **detail_snapshot,
            "lastChanges": last_changes,
        }
        performance_store.record_work_run(
            work_type="document_ingest" if work_label == "Document ingest" else "index_check",
            label=work_label,
            trigger_reason=reason,
            status=work_status,
            started_at=started_at,
            finished_at=finished_at,
            chunks=int(merged_details.get("chunks") or 0),
            images=int(merged_details.get("storedImages") or merged_details.get("extractedImages") or 0),
            dropped_chunks=int(merged_details.get("droppedChunks") or 0),
            details=merged_details,
            error_message=work_error,
        )
        run_index_housekeeping()
        INDEX_JOB_LOCK.release()


def start_index_check(reason="manual"):
    if INDEX_JOB_LOCK.locked():
        return {"started": False, "status": dict(index_status)}

    if reason != "watch":
        status = schedule_next_ingest_check()
        INGEST_WATCH_RESCHEDULE.set()
    else:
        status = dict(index_status)

    thread = threading.Thread(
        target=check_for_training_changes,
        kwargs={"reason": reason},
        name=f"circuitshelf-index-{reason}",
        daemon=True,
    )
    thread.start()
    return {"started": True, "status": status}


def ingest_watch_loop():
    schedule_next_ingest_check()
    trace_logger.info(f"👁️ Training watcher enabled. Checking every {ingest_watch_interval_seconds()} seconds.")

    while not INGEST_WATCH_STOP.is_set():
        remaining = seconds_until_next_ingest_check()
        if INGEST_WATCH_STOP.wait(remaining):
            break
        if INGEST_WATCH_RESCHEDULE.is_set():
            INGEST_WATCH_RESCHEDULE.clear()
            schedule_next_ingest_check()
            continue
        schedule_next_ingest_check()
        start_index_check("watch")


def start_ingest_watcher():
    global INGEST_WATCH_THREAD
    if not config.get("INGEST_WATCH_ENABLED", True):
        set_index_status(enabled=False)
        return
    if INGEST_WATCH_THREAD and INGEST_WATCH_THREAD.is_alive():
        return
    INGEST_WATCH_STOP.clear()
    INGEST_WATCH_THREAD = threading.Thread(target=ingest_watch_loop, name="circuitshelf-ingest-watch", daemon=True)
    INGEST_WATCH_THREAD.start()


def stop_ingest_watcher():
    INGEST_WATCH_STOP.set()


def apply_ingest_watch_enabled(value):
    if value:
        set_index_status(enabled=True)
        start_ingest_watcher()
    else:
        stop_ingest_watcher()
        set_index_status(enabled=False, nextCheckAt=None)


def apply_ingest_watch_interval(_value):
    schedule_next_ingest_check()
    INGEST_WATCH_RESCHEDULE.set()


runtime_settings.register_callback("INGEST_WATCH_ENABLED", apply_ingest_watch_enabled)
runtime_settings.register_callback("INGEST_WATCH_INTERVAL_SECONDS", apply_ingest_watch_interval)


@trace_timer("get_or_build_index")
def get_or_build_index():
    if not os.path.exists(TRAINING_DIR):
        trace_logger.error(f"❌ Training folder '{TRAINING_DIR}' not found! Cannot proceed.")
        exit(1)

    trace_logger.info("🔄 Starting index load or build...")
    start_time = time.time()
    manifest = build_ingest_manifest()
    current_manifest = manifest.scan()

    previous_manifest = vector_store.load_document_records()

    if previous_manifest:
        try:
            chunks, sources, metadata, embeddings = vector_store.load_state_payload()
            state.set_chunks(chunks)
            state.set_sources(sources)
            state.set_metadata(metadata)
            state.set_embeddings(embeddings)
            state.set_index(None)
            image_count = load_db_image_state()

            if not chunks or not embeddings:
                if vector_store.counts()["documents"] == 0 and vector_store.pending_review_count() > 0:
                    state.replace_catalog(
                        chunks=[],
                        sources=[],
                        metadata=[],
                        embeddings=[],
                        image_store={},
                        image_captions={},
                        image_page_text={},
                        image_mime_types={},
                        image_id_list=[],
                        index=None,
                    )
                    duration = time.time() - start_time
                    trace_logger.info(
                        "✅ DB has pending review documents but no approved catalog; "
                        f"serving empty active state in {duration:.2f} sec"
                    )
                    return
                raise ValueError("DB vector catalog is incomplete.")

            changes = manifest.diff(previous_manifest, current_manifest)
            if not changes.has_changes:
                image_counts = image_store.counts()
                if image_counts["referenced"] > image_counts["stored"]:
                    trace_logger.warning(
                        "⚠️ DB image catalog is incomplete; serving the existing text/vector catalog. "
                        "Run an index check to repair missing image rows."
                    )
                if image_counts["stored"] > image_counts["embeddings"]:
                    backfilled = backfill_missing_image_embeddings()
                    if backfilled:
                        image_count = load_db_image_state()
                duration = time.time() - start_time
                SystemInit.log_build_info(trace_logger, chunks, embeddings, state.get_image_id_list(), duration)
                trace_logger.info(f"✅ DB catalog loaded in {duration:.2f} sec with {image_count} image entries")
                return

            trace_logger.info(
                f"🔁 Training changes detected at startup. Added: {len(changes.added)}, "
                f"modified: {len(changes.modified)}, removed: {len(changes.removed)}, "
                f"unchanged: {len(changes.unchanged)}. Serving the DB catalog; "
                "watcher or manual Check now will ingest changes."
            )
            set_index_status(
                lastReason="startup",
                lastResult="training_changes_pending",
                lastChanges=file_changes_payload(changes),
            )
            duration = time.time() - start_time
            SystemInit.log_build_info(trace_logger, chunks, embeddings, state.get_image_id_list(), duration)
            trace_logger.info(f"✅ DB catalog loaded in {duration:.2f} sec with pending training changes")
            return
        except Exception as e:
            trace_logger.warning(f"🧹 DB catalog load failed, rebuilding from source documents: {e}")

    state.replace_catalog(
        chunks=[],
        sources=[],
        metadata=[],
        embeddings=[],
        image_store={},
        image_captions={},
        image_page_text={},
        image_mime_types={},
        image_id_list=[],
        index=None,
    )
    if current_manifest:
        set_index_status(
            lastReason="startup",
            lastResult="source_documents_waiting",
            lastChanges={
                "added": len(current_manifest),
                "modified": 0,
                "removed": 0,
                "unchanged": 0,
                "addedFiles": list(current_manifest.keys())[:20],
                "modifiedFiles": [],
                "removedFiles": [],
            },
        )
    duration = time.time() - start_time
    trace_logger.info(
        "✅ DB catalog is empty; serving empty state. "
        f"{len(current_manifest)} source files are waiting for upload/manual indexing. "
        f"Startup completed in {duration:.2f} sec"
    )


def image_asset_count_for_document(doc_source):
    return sum(
        1
        for image_id in state.get_image_store().keys()
        if image_asset_belongs_to_document(image_id, doc_source)
    )


document_intelligence_service = DocumentIntelligenceService(
    state=state,
    vector_store=vector_store,
    intelligence_store=intelligence_store,
    trace_logger=trace_logger,
    training_dir=TRAINING_DIR,
    display_source_name=display_source_name,
    document_source_from_metadata=document_source_from_metadata,
    image_asset_belongs_to_document=image_asset_belongs_to_document,
    extract_page_number=extract_page_number,
)


query_preprocessor = QueryPreprocessor(
    config=config,
    trace_logger=trace_logger,
    banned_phrases=BANNED_PHRASES,
)
runtime_chunk_mapper = RuntimeChunkMapper(
    state=state,
    vector_store=vector_store,
    trace_logger=trace_logger,
)
prompt_service = PromptService(
    config=config,
    prompt_dir=PROMPT_DIR,
    trace_logger=trace_logger,
    token_length=TokenUtils.tokenize_len,
)
ollama_chat_client = OllamaChatClient(
    config=config,
    trace_logger=trace_logger,
    api_url=OLLAMA_API_URL,
    default_system_prompt=RAG_CHAT_SYSTEM_PROMPT,
    default_temperature=LLM_TEMPERATURE,
    default_num_predict=LLM_NUM_PREDICT,
    default_num_ctx=LLM_NUM_CTX,
    post_timeout=POST_TIMEOUT,
    query_retries=QUERY_RETRIES,
    query_retry_delay=QUERY_RETRY_DELAY,
    max_chat_history_turns=MAX_CHAT_HISTORY_TURNS,
    max_chat_history_chars=MAX_CHAT_HISTORY_CHARS,
)


@trace_timer("query_ollama_chat with retry")
def query_ollama_chat_with_retry(prompt, model_name, chat_history=None, retries=None, delay=None, system_prompt=None):
    return ollama_chat_client.chat_with_retry(
        prompt,
        model_name,
        chat_history=chat_history,
        retries=retries,
        delay=delay,
        system_prompt=system_prompt,
    )


rag_service = RagService(
    state=state,
    trace_logger=trace_logger,
    embedder=embedder,
    vector_store=vector_store,
    chunker=chunker,
    reranker_engine=reranker_engine,
    prompt_service=prompt_service,
    query_preprocessor=query_preprocessor,
    runtime_chunk_mapper=runtime_chunk_mapper,
    response_cache=db_response_cache,
    query_log_store=query_log_store,
    openai_assist_service=openai_assist_service,
    document_intelligence_service=document_intelligence_service,
    image_retrieval_service=image_retrieval_service,
    build_source_payload=build_source_payload,
    query_llm=query_ollama_chat_with_retry,
    llm_model_options=LLM_MODEL_OPTIONS,
    default_llm_model=LLM_MODEL_NAME,
    max_chat_history_turns=MAX_CHAT_HISTORY_TURNS,
    max_chat_history_chars=MAX_CHAT_HISTORY_CHARS,
    response_finalizer_system_prompt=RESPONSE_FINALIZER_SYSTEM_PROMPT,
    response_finalizer_enabled=RESPONSE_FINALIZER_ENABLED,
    response_finalizer_mode=RESPONSE_FINALIZER_MODE,
    response_finalizer_min_confidence=RESPONSE_FINALIZER_MIN_CONFIDENCE,
    response_finalizer_max_context_chars=RESPONSE_FINALIZER_MAX_CONTEXT_CHARS,
)


runtime_status_reporter = RuntimeStatusReporter(
    config=config,
    state=state,
    vector_store=vector_store,
    image_store=image_store,
    response_cache=db_response_cache,
    performance_store=performance_store,
    database=database,
    embedding_model_name=EMBED_MODEL_NAME,
    reranker_model_name=CROSS_ENCODER_MODEL,
    llm_model_name=LLM_MODEL_NAME,
    detected_cpu_count_fn=detected_cpu_count,
    reserved_core_count_fn=reserved_core_count,
    usable_core_count_fn=usable_core_count,
    active_document_worker_count_fn=active_document_worker_count,
    index_status=index_status,
)


@asynccontextmanager
async def lifespan(_app):
    start_ingest_watcher()
    try:
        yield
    finally:
        stop_ingest_watcher()


app = create_circuitshelf_app(lifespan=lifespan)


def effective_embedding_batch_size():
    return runtime_effective_embedding_batch_size(config)


def session_timeout_seconds() -> int:
    return max(60, int(config.get("SESSION_TIMEOUT_SECONDS", config.get("SESSION_TTL_SECONDS", 28800))))


USER_PREFERENCE_KEYS = {"ask.retrieval", "ui.theme"}


auth_dependencies = AuthDependencyService(
    database=database,
    user_store=user_store,
    entity_store=entity_store,
    session_timeout_seconds=session_timeout_seconds,
)

api_dependencies = ApiDependencies(
    require_authenticated_user=auth_dependencies.require_authenticated_user,
    require_entity_member=auth_dependencies.require_entity_member,
    require_entity_admin=auth_dependencies.require_entity_admin,
    require_system_admin_user=auth_dependencies.require_system_admin_user,
    bearer_token_from_request=auth_dependencies.bearer_token_from_request,
    session_timeout_seconds=session_timeout_seconds,
    user_payload=auth_dependencies.user_payload,
    user_id_for_user=auth_dependencies.user_id_for_user,
    verify_user=auth_dependencies.verify_user,
    user_store=user_store,
    user_preferences_store=user_preferences_store,
    account_profile_store=account_profile_store,
    entity_store=entity_store,
    password_policy_store=password_policy_store,
    ai_provider_store=ai_provider_store,
    openai_model_service=openai_model_service,
    performance_store=performance_store,
)

document_management_service = DocumentManagementService(
    vector_store=vector_store,
    training_dir=TRAINING_DIR,
    trace_logger=trace_logger,
    prune_training_files_from_state=prune_training_files_from_state,
)


register_api_routes(
    app,
    api_dependencies=api_dependencies,
    user_preference_keys=USER_PREFERENCE_KEYS,
    config=config,
    models=LLM_MODEL_OPTIONS,
    default_model=LLM_MODEL_NAME,
    auth_configured=lambda: database.configured and user_store.has_active_users(),
    session_timeout_seconds=session_timeout_seconds,
    build_readiness_status=runtime_status_reporter.build_readiness_status,
    build_runtime_status=runtime_status_reporter.build_runtime_status,
    conversation_store=conversation_store,
    conversation_title_from_question=conversation_title_from_question,
    lab_inventory_store=lab_inventory_store,
    project_finder_store=project_finder_store,
    parse_inventory_import=parse_inventory_import,
    require_admin_user=auth_dependencies.require_admin_user,
    settings_store=settings_store,
    runtime_settings=runtime_settings,
    trace_logger=trace_logger,
    start_index_check=start_index_check,
    vector_store=vector_store,
    image_store=image_store,
    refresh_active_state_from_db=refresh_active_state_from_db,
    reindex_review_source=reindex_review_source,
    remove_document_from_store=document_management_service.remove_document_from_store,
    assembly_plan_store=assembly_plan_store,
    bench_tools=bench_tools,
    get_rag_response=rag_service.get_rag_response,
    query_ollama_chat_with_retry=query_ollama_chat_with_retry,
    normalize_sources_for_api=normalize_sources_for_api,
    build_recovery_prompt=build_recovery_prompt,
    parse_recovered_build_card=parse_recovered_build_card,
    recovery_system_prompt=RECOVERY_SYSTEM_PROMPT,
    username_for_user=auth_dependencies.username_for_user,
    training_dir=TRAINING_DIR,
    supported_training_extensions=supported_training_extensions,
    state=state,
    image_asset_belongs_to_document=image_asset_belongs_to_document,
    extract_page_number=extract_page_number,
    document_source_from_metadata=document_source_from_metadata,
    source_image_id_from_metadata=source_image_id_from_metadata,
    extract_pinout_map=extract_pinout_map,
    get_or_build_datasheet_intelligence=document_intelligence_service.get_or_build,
    display_source_name=display_source_name,
    sanitize_for_json=sanitize_for_json,
    get_last_trace=state.get_last_trace,
    flush_trace_log=trace_log_helper.flush,
    current_trace_log_file=trace_log_helper.current_file,
    tail_text_file=tail_text_file,
    performance_store=performance_store,
)


if __name__ == "__main__":

    app_host = config.get("APP_HOST", config.get("API_HOST", "127.0.0.1"))
    app_port = config.get("APP_PORT", config.get("API_PORT", 1964))
    server_pid_file = config.get("SERVER_PID_FILE", "data/circuitshelf.pid")

    try:
        with acquire_process_lock(server_pid_file, name="CircuitShelf"):
            cleanup_stale_tesseract_temp_files()
            get_or_build_index()

            mount_react_app(app, react_dist_dir=REACT_DIST_DIR, logger=trace_logger)
            trace_logger.info(f"🌐 CircuitShelf available at http://{app_host}:{app_port}")
            start_app_server(app, host=app_host, port=app_port)
    except ProcessLockError as exc:
        trace_logger.error(str(exc))
        raise SystemExit(1) from exc
