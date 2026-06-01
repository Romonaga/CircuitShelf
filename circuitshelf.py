# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 06:54:37 2025

@author: sueco, rew
"""


# ===  Imports, Logging, and Configuration ===

import os
import re
import time
import base64
import zipfile
import tempfile
import fitz  # PyMuPDF
import numpy as np
import pandas as pd
import threading
import bench_tools
from lxml import etree
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from docx import Document
from sentence_transformers import SentenceTransformer, CrossEncoder
from io import BytesIO
from PIL import Image
from nltk.tokenize import sent_tokenize
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.responses import JSONResponse



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
from backend.services.runtime_status_service import (
    RuntimeStatusReporter,
    effective_embedding_batch_size as runtime_effective_embedding_batch_size,
)
from backend.services.image_retrieval_service import ImageRetrievalService
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
from index_builder import IndexBuildResult, IndexBuilder
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
INDEX_IMAGE_OCR_AS_TEXT = config.get("INDEX_IMAGE_OCR_AS_TEXT", False)
OCR_INDEX_TEXT_MIN_CHARS = config.get("OCR_INDEX_TEXT_MIN_CHARS", 80)
USE_MULTITHREAD_OCR = config.get("USE_MULTITHREAD_OCR", False)
PDF_RENDER_VECTOR_PAGES = config.get("PDF_RENDER_VECTOR_PAGES", True)
PDF_RENDER_MAX_PAGES_PER_DOC = config.get("PDF_RENDER_MAX_PAGES_PER_DOC", 8)
PDF_RENDER_MIN_DRAWINGS = config.get("PDF_RENDER_MIN_DRAWINGS", 100)
PDF_RENDER_ZOOM = config.get("PDF_RENDER_ZOOM", 1.5)
PDF_RENDER_RASTER_PAGES = config.get("PDF_RENDER_RASTER_PAGES", True)
PDF_RENDER_MIN_RASTER_COVERAGE = config.get("PDF_RENDER_MIN_RASTER_COVERAGE", 0.8)
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
INDEX_PROGRESS_LOCK = threading.Lock()
ACTIVE_DOCUMENT_WORKERS_LOCK = threading.Lock()
ACTIVE_DOCUMENT_WORKERS = 0
INGEST_WATCH_STOP = threading.Event()
INGEST_WATCH_RESCHEDULE = threading.Event()
INGEST_WATCH_THREAD = None
index_status = {
    "enabled": bool(config.get("INGEST_WATCH_ENABLED", True)),
    "running": False,
    "stage": "idle",
    "currentFiles": [],
    "fileProgress": {},
    "processedFiles": 0,
    "totalFiles": 0,
    "lastStartedAt": None,
    "lastFinishedAt": None,
    "lastReason": None,
    "lastResult": "idle",
    "lastError": None,
    "lastChanges": None,
    "nextCheckAt": None,
    "details": {},
}


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


def cleanup_stale_tesseract_temp_files(max_age_seconds=TESSERACT_TEMP_MAX_AGE_SECONDS):
    temp_dir = tempfile.gettempdir()
    now = time.time()
    removed = 0
    failures = 0

    try:
        names = os.listdir(temp_dir)
    except OSError as exc:
        trace_logger.warning(f"Could not inspect temp directory for stale Tesseract files: {exc}")
        return {"removed": 0, "failures": 1}

    for name in names:
        if not name.startswith("tess_"):
            continue

        path = os.path.join(temp_dir, name)
        try:
            if not os.path.isfile(path):
                continue
            age_seconds = now - os.path.getmtime(path)
            if age_seconds < max_age_seconds:
                continue
            os.remove(path)
            removed += 1
        except OSError as exc:
            failures += 1
            trace_logger.debug(f"Could not remove stale Tesseract temp file {path}: {exc}")

    if removed or failures:
        trace_logger.info(
            f"Cleaned stale Tesseract temp files. Removed: {removed}, failures: {failures}"
        )
    return {"removed": removed, "failures": failures}


def cleanup_expired_trace_logs():
    return cleanup_old_logs(
        configured_log_file=TRACE_LOG_FILE,
        active_log_file=trace_log_helper.current_file(),
        retention_days=LOG_RETENTION_DAYS,
        logger=trace_logger,
    )


def run_index_housekeeping():
    try:
        cleanup_stale_tesseract_temp_files()
    except Exception as exc:
        trace_logger.warning(f"Index housekeeping could not clean stale Tesseract temp files: {exc}")

    try:
        cleanup_expired_trace_logs()
    except Exception as exc:
        trace_logger.warning(f"Index housekeeping could not clean expired trace logs: {exc}")


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def utc_now():
    return datetime.now(timezone.utc)


def set_index_status(**updates):
    with INDEX_PROGRESS_LOCK:
        index_status.update(updates)
        return dict(index_status)


def ingest_watch_interval_seconds():
    return max(30, int(config.get("INGEST_WATCH_INTERVAL_SECONDS", 300)))


def schedule_next_ingest_check(interval=None):
    interval_seconds = interval if interval is not None else ingest_watch_interval_seconds()
    next_check = datetime.now(timezone.utc).timestamp() + interval_seconds
    return set_index_status(
        nextCheckAt=datetime.fromtimestamp(next_check, timezone.utc).isoformat()
    )


def seconds_until_next_ingest_check(interval=None):
    with INDEX_PROGRESS_LOCK:
        next_check_at = index_status.get("nextCheckAt")
    if not next_check_at:
        status = schedule_next_ingest_check(interval)
        next_check_at = status["nextCheckAt"]
    try:
        next_check = datetime.fromisoformat(next_check_at).timestamp()
    except (TypeError, ValueError):
        status = schedule_next_ingest_check(interval)
        next_check = datetime.fromisoformat(status["nextCheckAt"]).timestamp()
    return max(0, next_check - datetime.now(timezone.utc).timestamp())


def update_index_progress(*, stage=None, current_file=None, finished_file=None, total_files=None, details=None, file_details=None):
    with INDEX_PROGRESS_LOCK:
        active_files = list(index_status.get("currentFiles") or [])
        file_progress = dict(index_status.get("fileProgress") or {})
        if total_files is not None:
            index_status["totalFiles"] = int(total_files)
        if stage is not None:
            index_status["stage"] = stage
        if details is not None:
            index_status["details"] = details
        if current_file and current_file not in active_files:
            active_files.append(current_file)
            file_progress.setdefault(current_file, {})
        if current_file and file_details is not None:
            current_progress = dict(file_progress.get(current_file) or {})
            current_progress.update({key: value for key, value in file_details.items() if value is not None})
            file_progress[current_file] = current_progress
        if finished_file:
            active_files = [name for name in active_files if name != finished_file]
            file_progress.pop(finished_file, None)
            index_status["processedFiles"] = int(index_status.get("processedFiles") or 0) + 1
        index_status["currentFiles"] = active_files
        index_status["fileProgress"] = {name: file_progress.get(name, {}) for name in active_files}
        return dict(index_status)


def update_index_detail(**updates):
    with INDEX_PROGRESS_LOCK:
        details = dict(index_status.get("details") or {})
        details.update({key: value for key, value in updates.items() if value is not None})
        index_status["details"] = details
        return dict(index_status)


def begin_document_worker() -> int:
    global ACTIVE_DOCUMENT_WORKERS
    with ACTIVE_DOCUMENT_WORKERS_LOCK:
        ACTIVE_DOCUMENT_WORKERS += 1
        return ACTIVE_DOCUMENT_WORKERS


def finish_document_worker() -> int:
    global ACTIVE_DOCUMENT_WORKERS
    with ACTIVE_DOCUMENT_WORKERS_LOCK:
        ACTIVE_DOCUMENT_WORKERS = max(0, ACTIVE_DOCUMENT_WORKERS - 1)
        return ACTIVE_DOCUMENT_WORKERS


def current_document_workers() -> int:
    with ACTIVE_DOCUMENT_WORKERS_LOCK:
        return max(1, ACTIVE_DOCUMENT_WORKERS)


def active_document_worker_count() -> int:
    with ACTIVE_DOCUMENT_WORKERS_LOCK:
        return ACTIVE_DOCUMENT_WORKERS


def source_ingest_scope(source):
    scope = vector_store.ingest_scope_overrides([source]).get(source)
    if not scope:
        scope = vector_store.document_scopes_for_sources([source]).get(source)
    is_global = bool(scope.get("is_global", True)) if scope else True
    return {
        "is_global": is_global,
        "entity_id": None if is_global else scope.get("entity_id"),
        "created_by_user_id": scope.get("created_by_user_id") if scope else None,
    }


def sample_ingested_text(target_state, rel_path, max_chars=6000):
    samples = []
    for chunk, source, meta in zip(target_state.get_chunks(), target_state.get_sources(), target_state.get_metadata()):
        meta = meta or {}
        if vector_store.rel_path_for_source(source, meta) != rel_path:
            continue
        text = str(chunk or "").strip()
        if text:
            samples.append(text)
        if sum(len(item) for item in samples) >= max_chars:
            break
    return "\n\n".join(samples)[:max_chars]


def maybe_review_ingestion_with_openai(source, ingested_state, document_stats):
    if not config.get("INGEST_OPENAI_ASSIST_ENABLED", False):
        return None
    scope = source_ingest_scope(source)
    stats = (document_stats or {}).get(source, {})
    result = openai_assist_service.review_ingestion(
        source_path=source,
        is_global=bool(scope["is_global"]),
        entity_id=scope.get("entity_id"),
        user_id=scope.get("created_by_user_id"),
        stats=stats,
        sample_text=sample_ingested_text(ingested_state, source),
        enabled=True,
    )
    if result:
        trace_logger.info(
            f"🤖 OpenAI ingestion review stored for {source} "
            f"using {result.get('paidBy')} billing (${float(result.get('estimatedCost') or 0):.6f})."
        )
    return result


def build_ingest_context():
    ingest_state = StateManager(use_lock=True, cache_capacity=0, trace_logger=trace_logger)
    ingest_token_utils = TokenUtils(state=ingest_state, trace_logger=trace_logger)
    ingest_chunker = ChunkingUtils(
        state=ingest_state,
        token_utils=ingest_token_utils,
        config=config,
        trace_logger=trace_logger,
    )
    return ingest_state, ingest_token_utils, ingest_chunker


def source_matches_training_file(candidate, rel_path):
    if not candidate:
        return False

    candidate = os.path.normpath(str(candidate))
    rel_path = os.path.normpath(rel_path)
    full_path = os.path.normpath(os.path.join(TRAINING_DIR, rel_path))
    base_name = os.path.basename(rel_path)
    candidate_base = os.path.basename(candidate)

    return (
        candidate == rel_path
        or candidate == full_path
        or candidate_base == base_name
        or candidate_base.startswith(f"{base_name}_page")
        or candidate_base.startswith(f"{base_name}_textbox")
    )


def prune_training_files_from_state(rel_paths):
    if not rel_paths:
        return

    rel_paths = set(rel_paths)

    def matches_any(candidate):
        return any(source_matches_training_file(candidate, rel_path) for rel_path in rel_paths)

    kept_chunks, kept_sources, kept_metadata = [], [], []
    kept_embeddings = []
    embeddings = state.get_embeddings()
    removed_chunks = 0
    for idx, (chunk, source, meta) in enumerate(zip(state.get_chunks(), state.get_sources(), state.get_metadata())):
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
        for key, value in state.get_image_store().items()
        if not matches_any(key)
    }
    image_captions = {
        key: value
        for key, value in state.get_image_captions().items()
        if not matches_any(key)
    }
    image_page_text = {
        key: value
        for key, value in state.get_image_page_text().items()
        if not matches_any(key)
    }
    image_mime_types = {
        key: value
        for key, value in state.get_image_mime_types().items()
        if not matches_any(key)
    }
    image_id_list = [
        img_id for img_id in state.get_image_id_list()
        if not matches_any(img_id)
    ]

    state.replace_catalog(
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

    trace_logger.info(
        f"🧹 Pruned {removed_chunks} chunks and removed OCR/image state for "
        f"{len(rel_paths)} changed/removed training files."
    )


def load_db_image_state():
    image_data, captions, page_text, mime_types = image_store.load_state_payload()
    state.set_image_store(image_data)
    state.set_image_captions(captions)
    state.set_image_page_text(page_text)
    state.set_image_mime_types(mime_types)
    builder = IndexBuilder(state, chunker, embedder, config, trace_logger, batch_size_resolver=effective_embedding_batch_size)
    return builder.build_image_index()


def refresh_active_state_from_db():
    chunks, sources, metadata, embeddings = vector_store.load_state_payload()
    state.replace_catalog(
        chunks=chunks,
        sources=sources,
        metadata=metadata,
        embeddings=embeddings,
        image_store={},
        image_captions={},
        image_page_text={},
        image_mime_types={},
        image_id_list=[],
    )
    return load_db_image_state()


def persist_db_image_state(file_records, target_state=None, rel_paths=None, progress_file=None):
    target_state = target_state or state
    image_text = target_state.get_image_page_text()
    image_ids = target_state.get_image_id_list()
    image_payload = target_state.get_image_store()
    total_images = len(image_payload)
    if not progress_file:
        update_index_detail(
            savedImages=0,
            totalImagesToSave=total_images,
            skippedImages=0,
            indexedImageTexts=len(image_ids),
        )
    if progress_file:
        update_index_progress(
            current_file=progress_file,
            file_details={
                "documentPhase": "Preparing image save",
                "savedImages": 0,
                "totalImagesToSave": total_images,
                "skippedImages": 0,
            },
        )
    image_embeddings = {}
    if image_ids:
        if not progress_file:
            update_index_detail(imageEmbeddingTexts=0, imageEmbeddingTotal=len(image_ids))
        if progress_file:
            update_index_progress(
                current_file=progress_file,
                file_details={
                    "documentPhase": "Embedding image text",
                    "imageEmbeddingTexts": 0,
                    "imageEmbeddingTotal": len(image_ids),
                },
            )
        encoded = embedder.encode(
            [image_text[key] for key in image_ids],
            batch_size=effective_embedding_batch_size(),
            convert_to_numpy=True,
        ).astype("float32")
        image_embeddings = {key: encoded[idx] for idx, key in enumerate(image_ids)}
        if not progress_file:
            update_index_detail(imageEmbeddingTexts=len(image_ids), imageEmbeddingTotal=len(image_ids))
        if progress_file:
            update_index_progress(
                current_file=progress_file,
                file_details={
                    "imageEmbeddingTexts": len(image_ids),
                    "imageEmbeddingTotal": len(image_ids),
                },
            )

    def report_image_save_progress(saved_images, total_images, skipped_images=0, current_image=None):
        if progress_file:
            update_index_progress(
                current_file=progress_file,
                file_details={
                    "documentPhase": "Saving images",
                    "savedImages": saved_images,
                    "totalImagesToSave": total_images,
                    "skippedImages": skipped_images,
                    "currentImage": current_image,
                },
            )
        else:
            update_index_detail(
                savedImages=saved_images,
                totalImagesToSave=total_images,
                skippedImages=skipped_images,
            )

    payload = {
        "file_records": file_records,
        "image_store": image_payload,
        "image_captions": target_state.get_image_captions(),
        "image_page_text": target_state.get_image_page_text(),
        "image_embeddings": image_embeddings,
        "embedding_model": EMBED_MODEL_NAME,
        "metadata": target_state.get_metadata(),
        "progress_callback": report_image_save_progress,
    }
    if rel_paths is None:
        image_store.replace_catalog(**payload)
    else:
        image_store.upsert_sources(**payload, rel_paths=set(rel_paths))
    return {
        "storedImages": len(target_state.get_image_store()),
        "indexedImageTexts": len(image_ids),
        "ocrImageTexts": len(image_text),
    }


def backfill_missing_image_embeddings(limit=512):
    missing = image_store.load_missing_embedding_inputs(limit=limit)
    if not missing:
        return 0
    trace_logger.info(f"🖼️ Backfilling {len(missing)} missing DB image embeddings.")
    encoded = embedder.encode(
        [row["embedding_text"] for row in missing],
        batch_size=effective_embedding_batch_size(),
        convert_to_numpy=True,
    ).astype("float32")
    image_store.update_embeddings(
        {row["image_key"]: encoded[idx] for idx, row in enumerate(missing)},
        EMBED_MODEL_NAME,
    )
    return len(missing)


def ocr_image_bytes(image_bytes, image_id):
    """Run the single OCR acceptance path used by all image ingestion."""
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    result = run_ocr(image, config)
    if result.skipped:
        return {
            "accepted": False,
            "text": "",
            "score": 0.0,
            "reason": result.skip_reason,
            "confidence": result.confidence,
            "skipped": True,
        }

    cleaned_text = chunker.clean_ocr_text(result.text)
    score, reason = chunker.evaluate_ocr_quality(cleaned_text, result.confidence)
    accepted = score >= config.get("OCR_TXT_DROP_SCORE", 0.4)
    return {
        "accepted": accepted,
        "text": cleaned_text,
        "score": score,
        "reason": reason,
        "confidence": result.confidence,
        "skipped": False,
    }


def format_confidence(confidence):
    return f", confidence: {confidence:.1f}" if confidence is not None else ""


def image_bytes_to_png_bytes(image_bytes, image_id="image"):
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()
    except Exception as e:
        trace_logger.warning(f"⚠️ Could not normalize {image_id} to PNG for web display: {e}")
        return image_bytes


def get_ocr_worker_count(item_count):
    if not USE_MULTITHREAD_OCR or item_count <= 1:
        return 1
    return ocr_worker_count(
        item_count,
        active_document_workers=current_document_workers(),
        cpu_count=detected_cpu_count(),
    )


def ocr_pdf_image_job(job):
    order, page_num, img_index, image_bytes, img_name = job
    ocr_result = ocr_image_bytes(image_bytes, img_name)
    web_image_bytes = image_bytes_to_png_bytes(image_bytes, img_name) if ocr_result["accepted"] else None
    return {
        "order": order,
        "page_num": page_num,
        "img_index": img_index,
        "image_bytes": image_bytes,
        "img_name": img_name,
        "ocr_result": ocr_result,
        "web_image_bytes": web_image_bytes,
    }


def run_pdf_image_ocr_jobs(image_jobs):
    if not image_jobs:
        return []

    worker_count = get_ocr_worker_count(len(image_jobs))
    if worker_count == 1:
        return [ocr_pdf_image_job(job) for job in image_jobs]

    trace_logger.info(
        f"🧵 OCR processing {len(image_jobs)} PDF images with {worker_count} workers "
        f"({detected_cpu_count()} cores, reserving {reserved_core_count()} cores, "
        f"{current_document_workers()} active document workers)"
    )
    results = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(ocr_pdf_image_job, job): job for job in image_jobs}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as ex:
                job = futures[future]
                trace_logger.warning(f"❌ OCR worker failed for {job[4]}: {ex}")

    results.sort(key=lambda item: item["order"])
    return results


def should_report_page_progress(page_number, total_pages, last_reported, min_interval=10):
    if page_number <= 1 or page_number >= total_pages:
        return True
    return page_number - last_reported >= min_interval


def add_pdf_rendered_pages(path, target_state, progress_callback=None):
    if not PDF_RENDER_VECTOR_PAGES:
        return 0

    if progress_callback:
        progress_callback(
            currentDocument=os.path.basename(path),
            documentPhase="Selecting visual PDF pages",
        )
    try:
        rendered_pages = render_pdf_visual_pages(
            path,
            max_pages=int(PDF_RENDER_MAX_PAGES_PER_DOC or 0),
            min_drawings=int(PDF_RENDER_MIN_DRAWINGS or 100),
            zoom=float(PDF_RENDER_ZOOM or 1.5),
            render_raster_pages=bool(PDF_RENDER_RASTER_PAGES),
            min_raster_coverage=float(PDF_RENDER_MIN_RASTER_COVERAGE or 0.8),
        )
    except Exception as exc:
        trace_logger.warning(f"⚠️ Could not render visual PDF pages for {path}: {exc}")
        return 0

    for rendered_page in rendered_pages:
        if progress_callback:
            progress_callback(
                currentDocument=os.path.basename(path),
                documentPhase="Saving rendered PDF pages",
                pdfPage=rendered_page.page_number,
            )
        target_state.add_image_store(
            rendered_page.image_key,
            base64.b64encode(rendered_page.image_bytes).decode("utf-8"),
        )
        target_state.add_image_caption(rendered_page.image_key, rendered_page.caption)
        target_state.add_image_page_text(rendered_page.image_key, rendered_page.searchable_text)

    if rendered_pages:
        trace_logger.info(f"🖼️ Rendered {len(rendered_pages)} vector-heavy PDF pages for {os.path.basename(path)}")
    return len(rendered_pages)


@trace_timer("load_pdf_text")
def load_pdf_text(path, target_state=None, progress_callback=None):
    """
    Extract text and images from a PDF file, perform OCR on images, and save images to a folder.
    """
    target_state = target_state or state
    trace_logger.info(f"📅 Loading PDF: {path}")
    pdf = fitz.open(path)
    page_texts = []
    extra_chunks, extra_sources, extra_meta = [], [], []
    image_jobs = []

    total_pages = len(pdf)
    last_reported_page = 0
    for page_num in range(total_pages):
        page_number = page_num + 1
        if progress_callback and should_report_page_progress(page_number, total_pages, last_reported_page):
            last_reported_page = page_number
            progress_callback(
                currentDocument=os.path.basename(path),
                documentPhase="Scanning PDF pages",
                pdfPage=page_number,
                pdfPages=total_pages,
                imageCandidates=len(image_jobs),
            )
        page = pdf[page_num]
        page_text = page.get_text().strip()
        page_texts.append(page_text)

        for img_index, img in enumerate(page.get_images(full=True)):
            try:
                xref = img[0]
                base_image = pdf.extract_image(xref)
                image_bytes = base_image["image"]
                img_name = f"{os.path.basename(path)}_page{page_number}_img{img_index+1}"
                image_jobs.append((len(image_jobs), page_num, img_index, image_bytes, img_name))

            except Exception as ex:
                trace_logger.warning(f"❌ Failed to process image on page {page_number}: {ex}")
                continue

    if progress_callback:
        progress_callback(
            currentDocument=os.path.basename(path),
            documentPhase="OCR image extraction",
            pdfPage=total_pages,
            pdfPages=total_pages,
            imageCandidates=len(image_jobs),
        )
    for result in run_pdf_image_ocr_jobs(image_jobs):
        page_num = result["page_num"]
        img_name = result["img_name"]
        ocr_result = result["ocr_result"]
        if not ocr_result["accepted"]:
            log_fn = trace_logger.debug if ocr_result["skipped"] else trace_logger.warning
            score = ocr_result["score"]
            reason = ocr_result["reason"]
            log_fn(f"⚠️ Dropped {img_name} — OCR score: {score:.2f}, reason: {reason}")
            continue

        ocr_text = ocr_result["text"]
        score = ocr_result["score"]
        confidence = ocr_result["confidence"]
        web_image_bytes = result["web_image_bytes"]

        trace_logger.info(f"🧠 OCR accepted for {img_name}: {len(ocr_text)} chars | score: {score:.2f}{format_confidence(confidence)}")

        target_state.add_image_store(img_name, base64.b64encode(web_image_bytes).decode("utf-8"))
        target_state.add_image_caption(img_name, f"Image from {os.path.basename(path)}, page {page_num+1}")

        target_state.add_image_page_text(img_name, ocr_text)
        if INDEX_IMAGE_OCR_AS_TEXT and len(ocr_text) >= OCR_INDEX_TEXT_MIN_CHARS:
            extra_chunks.append(ocr_text)
            extra_sources.append(path)
            ocr_meta = chunker.make_chunk_meta(ocr_text, path, "Image OCR", "ocr")
            ocr_meta.update({
                "page": page_num + 1,
                "parent_source": path,
                "source_image_id": img_name,
                "ocr_score": score,
                "ocr_confidence": confidence,
            })
            extra_meta.append(ocr_meta)

    add_pdf_rendered_pages(path, target_state, progress_callback=progress_callback)

    return page_texts, extra_chunks, extra_sources, extra_meta

@trace_timer("extract_images_from_docx_textboxes")
def extract_images_from_docx_textboxes(path):
    """
    Extract images from Word textboxes (VML), OCR them, and save to a folder.
    """
    base_doc = os.path.basename(path)
    all_chunks = []
    all_meta = []

    try:
        with open(path, "rb") as file:
            docx_content = file.read()
        with zipfile.ZipFile(BytesIO(docx_content)) as docx_zip:
            rels = {}
            for name in docx_zip.namelist():
                if name.startswith("word/_rels/") and name.endswith(".xml.rels"):
                    rel_tree = etree.fromstring(docx_zip.read(name))
                    for rel in rel_tree.xpath("//rel:Relationship", namespaces={"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}):
                        rid = rel.attrib["Id"]
                        target = rel.attrib["Target"]
                        rels[rid] = os.path.normpath(os.path.join(os.path.dirname(name), target))

            document_xml = docx_zip.read("word/document.xml")
            tree = etree.fromstring(document_xml)
            namespaces = {
                "v": "urn:schemas-microsoft-com:vml",
                "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            }

            v_images = tree.xpath(".//v:imagedata", namespaces=namespaces)
            for idx, v_img in enumerate(v_images):
                r_embed = v_img.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                if r_embed and r_embed in rels:
                    img_path = "word/" + rels[r_embed].replace("\\", "/")
                    if img_path in docx_zip.namelist():
                        img_data = docx_zip.read(img_path)
                        img_name = f"{base_doc}_textbox_img{idx+1}"
                    
                        try:
                            ocr_result = ocr_image_bytes(img_data, img_name)
                            if not ocr_result["accepted"]:
                                log_fn = trace_logger.debug if ocr_result["skipped"] else trace_logger.warning
                                log_fn(
                                    f"⚠️ Dropping textbox image {img_name} due to low OCR quality: "
                                    f"{ocr_result['score']:.2f} | {ocr_result['reason']}"
                                )
                                continue
                            ocr_text = ocr_result["text"]
                            web_img_data = image_bytes_to_png_bytes(img_data, img_name)
                            state.add_image_store(img_name, base64.b64encode(web_img_data).decode("utf-8"))
                            state.add_image_caption(img_name, f"Textbox image in {base_doc}")
                            state.add_image_page_text(img_name, ocr_text)

                            score = ocr_result["score"]
                            confidence = ocr_result["confidence"]
                            
                            use_adaptive = config.get("USE_ADAPTIVE_CHUNKING", False)
                            trace_logger.info(
                                f"🧠 Textbox OCR accepted for {img_name}: {len(ocr_text)} chars | "
                                f"score: {score:.2f}{format_confidence(confidence)} Using Adaptive: {use_adaptive}"
                            )
                            if use_adaptive:
                                chunks, meta = chunker.adaptive_chunk_text(ocr_text, base_doc)
                            else:
                                chunks, meta = chunker.smart_chunk_text(ocr_text, base_doc)

                            for m in meta:
                                ocr_meta = chunker.make_chunk_meta(
                                    ocr_text,
                                    base_doc,
                                    "Textbox OCR",
                                    "ocr",
                                )
                                ocr_meta.update(m)
                                ocr_meta.update({
                                    "section": "Textbox OCR",
                                    "source_image_id": img_name,
                                    "ocr_score": score,
                                    "ocr_confidence": confidence,
                                    "source": base_doc
                                })
                                m.clear()
                                m.update(ocr_meta)

                            all_chunks.extend(chunks)
                            all_meta.extend(meta)

                        except Exception as e:
                            trace_logger.warning(f"⚠️ Failed OCR for DOCX textbox {img_name}: {e}")

        return all_chunks, all_meta

    except Exception as e:
        trace_logger.warning(f"❌ Failed to extract DOCX textbox images from {path}: {e}")
        return [], []
def extract_page_number(s):
    match = re.search(r'_page(\d+)', s)
    return int(match.group(1)) if match else 0

def extract_first_number(s):
    match = re.search(r'(\d+)', s)
    return int(match.group(1)) if match else 0




@trace_timer("process_docx_file")
def process_docx_file(fpath, state, trace_logger, chunker, token_utils):
    doc = Document(fpath)
    text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    density = token_utils.estimate_token_density(text)
    if density > 40:
        trace_logger.warning(f"⚠️ High token density in {fpath}: {density:.2f} tokens/line")

    use_adaptive = config.get("USE_ADAPTIVE_CHUNKING", False)
    if use_adaptive:
        chunks, meta = chunker.adaptive_chunk_text(text, fpath)
    else:
        chunks, meta = chunker.smart_chunk_text(text, fpath)

    state.extend_chunks(chunks, [fpath] * len(chunks), meta)

    # Handle images in the document
    img_chunks, img_meta = extract_images_from_docx_textboxes(fpath)
    state.extend_chunks(img_chunks, [fpath] * len(img_chunks), img_meta)


@trace_timer("process_pdf_file")
def process_pdf_file(fpath, state, trace_logger, chunker, token_utils, progress_callback=None):
    page_texts, img_chunks, img_sources, img_meta = load_pdf_text(fpath, state, progress_callback=progress_callback)
    text = "\n\n".join(page_texts)
    density = token_utils.estimate_token_density(text)
    if density > 40:
        trace_logger.warning(f"⚠️ High token density in {fpath}: {density:.2f} tokens/line")

    use_adaptive = config.get("USE_ADAPTIVE_CHUNKING", False)
    if use_adaptive:
        chunks, meta = chunker.adaptive_chunk_pages(page_texts, fpath)
    else:
        chunks, meta = chunker.smart_chunk_pages(page_texts, fpath)

    linked_visuals = link_chunks_to_rendered_pages(
        chunks,
        meta,
        fpath,
        state.get_image_store().keys(),
    )
    if linked_visuals:
        trace_logger.info(f"🔗 Linked {linked_visuals} text chunks to rendered PDF page images for {os.path.basename(fpath)}")

    state.extend_chunks(chunks + img_chunks, [fpath] * len(chunks) + img_sources, meta + img_meta)

@trace_timer("process_text_file")
def process_text_file(fpath, state, trace_logger, chunker, token_utils):
    """
    Processes .txt and .md files by extracting text and chunking it.
    """
    try:
        with open(fpath, "r", encoding="utf-8") as file:
            text = file.read()

        density = token_utils.estimate_token_density(text)
        if density > 40:
            trace_logger.warning(f"⚠️ High token density in {fpath}: {density:.2f} tokens/line")

        use_adaptive = config.get("USE_ADAPTIVE_CHUNKING", False)
        if use_adaptive:
            chunks, meta = chunker.adaptive_chunk_text(text, fpath)
        else:
            chunks, meta = chunker.smart_chunk_text(text, fpath)

        state.extend_chunks(chunks, [fpath] * len(chunks), meta)
        trace_logger.info(f"✅ Processed text file: {fpath}")

    except Exception as e:
        trace_logger.error(f"❌ Failed to process text file {fpath}: {e}")


@trace_timer("process_image_file")
def process_image_file(fpath, state, trace_logger, chunker, token_utils=None):
    """
    Processes image files by performing OCR and saving the extracted text.
    """
    try:
        with open(fpath, "rb") as img_file:
            img_data = img_file.read()

        img_name = os.path.basename(fpath)
        ocr_result = ocr_image_bytes(img_data, img_name)
        if not ocr_result["accepted"]:
            log_fn = trace_logger.debug if ocr_result["skipped"] else trace_logger.warning
            log_fn(f"⚠️ Dropped {img_name} due to low OCR quality: {ocr_result['score']:.2f} | {ocr_result['reason']}")
            return

        ocr_text = ocr_result["text"]
        score = ocr_result["score"]
        confidence = ocr_result["confidence"]
        web_img_data = image_bytes_to_png_bytes(img_data, img_name)
        state.add_image_store(img_name, base64.b64encode(web_img_data).decode("utf-8"))
        state.add_image_caption(img_name, f"Image: {img_name}")
        state.add_image_page_text(img_name, ocr_text)
        state.add_image_id(img_name)

        trace_logger.info(f"🧠 OCR accepted for {img_name}: {len(ocr_text)} chars | score: {score:.2f}{format_confidence(confidence)}")

        # Chunk OCR text
        use_adaptive = config.get("USE_ADAPTIVE_CHUNKING", False)
        if use_adaptive:
            chunks, meta = chunker.adaptive_chunk_text(ocr_text, img_name)
        else:
            chunks, meta = chunker.smart_chunk_text(ocr_text, img_name)

        for m in meta:
            ocr_meta = chunker.make_chunk_meta(
                ocr_text,
                img_name,
                "Image OCR",
                "ocr",
            )
            ocr_meta.update(m)
            ocr_meta.update({
                "section": "Image OCR",
                "source_image_id": img_name,
                "ocr_score": score,
                "ocr_confidence": confidence,
                "source": img_name
            })
            m.clear()
            m.update(ocr_meta)

        state.extend_chunks(chunks, [img_name] * len(chunks), meta)
        trace_logger.info(f"✅ Processed image file: {fpath}")

    except Exception as e:
        trace_logger.error(f"❌ Failed to process image file {fpath}: {e}")


#### FILE PROCESSING BEINGES HERE ####
# Define FILE_PROCESSORS as a dictionary in Python
FILE_PROCESSORS = {
    ".docx": process_docx_file,
    ".pdf": process_pdf_file,
    ".md": process_text_file,
    ".txt": process_text_file,
    ".png": process_image_file,
    ".jpg": process_image_file,
    ".jpeg": process_image_file,
}

@trace_timer("process_file_by_type")
def process_file_by_type(fpath, state, trace_logger, chunker, token_utils, progress_callback=None):
    
    if os.path.isdir(fpath):
        trace_logger.warning(f"⚠️ Skipping directory: {fpath}")
        return
    
    ext = os.path.splitext(fpath)[1].lower()
    trace_logger.debug(f"Processing file: {fpath} with extension: {ext}")

    if ext == PDF_EXT:
        process_pdf_file(fpath, state, trace_logger, chunker, token_utils, progress_callback=progress_callback)
    elif ext in FILE_PROCESSORS:
        FILE_PROCESSORS[ext](fpath, state, trace_logger, chunker, token_utils)
    else:
        trace_logger.warning(f"⚠️ Unsupported file type: {ext} for File: {fpath}")


@trace_timer("load_documents_parallel")
def load_documents_parallel(
    folder,
    files_selected,
    clear_existing=True,
    target_state=None,
    target_chunker=None,
    target_token_utils=None,
    progress_callback=None,
):
    target_state = target_state or state
    target_chunker = target_chunker or chunker
    target_token_utils = target_token_utils or token_utils
    trace_logger.info(f"⚡ Starting threaded document loading from '{folder}'")
    
    if not os.path.exists(folder):
        trace_logger.error("❌ Training folder not found.")
        return
    
    if isinstance(files_selected, list):
        file_list = files_selected
    else:
        file_list = []
        recursive = config.get("TRAINING_RECURSIVE", True)
        excluded_dirs = set(config.get("TRAINING_EXCLUDE_DIRS", []))

        if recursive:
            for root, dirnames, filenames in os.walk(folder):
                dirnames[:] = [
                    dirname for dirname in dirnames
                    if dirname not in excluded_dirs and os.path.relpath(os.path.join(root, dirname), folder) not in excluded_dirs
                ]
                for fname in filenames:
                    if fname.startswith("~$"):
                        continue
                    fpath = os.path.join(root, fname)
                    if os.path.getsize(fpath) > 0:
                        file_list.append(os.path.relpath(fpath, folder))
        else:
            file_list = [
                fname for fname in os.listdir(folder)
                if not fname.startswith("~$") and os.path.isfile(os.path.join(folder, fname)) and os.path.getsize(os.path.join(folder, fname)) > 0
            ]

    file_list.sort(key=extract_first_number)
    if progress_callback:
        progress_callback(stage="processing_documents", total_files=len(file_list))
    if clear_existing:
        target_state.clear_all()

    if not file_list:
        trace_logger.warning(f"⚠️ No supported documents found in '{folder}'.")
        return


    def process_file(fname):
        fpath = fname if os.path.isabs(fname) else os.path.join(folder, fname)
        active_count = begin_document_worker()
        try:
            if progress_callback:
                progress_callback(stage="processing_documents", current_file=fname)
            thread_id = threading.get_ident()
            trace_logger.info(f"🛠️ Thread-{thread_id} started for {fname} ({active_count} active document workers)")
            start = time.time()

            detail_progress = None
            if progress_callback:
                def detail_progress(**details):
                    progress_callback(stage="processing_documents", current_file=fname, file_details=details)

            process_file_by_type(
                fpath,
                target_state,
                trace_logger,
                target_chunker,
                target_token_utils,
                progress_callback=detail_progress,
            )

            elapsed = time.time() - start
            trace_logger.info(f"✅ Thread-{thread_id} finished {fname} in {elapsed:.2f}s")

        except Exception as e:
            trace_logger.error(f"❌ Error processing {fname}: {e}")
        finally:
            if progress_callback:
                progress_callback(stage="processing_documents", finished_file=fname)
            finish_document_worker()

    cpu_count = detected_cpu_count()
    max_workers = document_worker_count(len(file_list), cpu_count=cpu_count)
    trace_logger.info(
        f"⚙️ Ingest worker budget: {cpu_count} cores detected, reserving {reserved_core_count(cpu_count)}, "
        f"{usable_core_count(cpu_count)} usable, {max_workers} document workers for {len(file_list)} files."
    )
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_file, fname): fname for fname in file_list}
        for future in as_completed(futures):
            future.result()

    if config.get("ENABLE_TOKEN_NORMALIZATION", False):
        target_token_utils.normalize_token_distribution()
    trace_logger.info(
        f"🚀 Finished loading. {len(target_state.get_chunks())} chunks, "
        f"{len(target_state.get_image_page_text())} accepted image OCR texts."
    )


def extract_document_for_incremental_ingest(source):
    ingested_state, ingest_token_utils, ingest_chunker = build_ingest_context()
    fpath = source if os.path.isabs(source) else os.path.join(TRAINING_DIR, source)
    active_count = begin_document_worker()
    try:
        update_index_progress(
            stage="processing_documents",
            current_file=source,
            file_details={"documentPhase": "Starting"},
        )
        thread_id = threading.get_ident()
        trace_logger.info(f"🛠️ Thread-{thread_id} started for {source} ({active_count} active document workers)")
        start = time.time()

        def detail_progress(**details):
            update_index_progress(stage="processing_documents", current_file=source, file_details=details)

        process_file_by_type(
            fpath,
            ingested_state,
            trace_logger,
            ingest_chunker,
            ingest_token_utils,
            progress_callback=detail_progress,
        )
        if config.get("ENABLE_TOKEN_NORMALIZATION", False):
            ingest_token_utils.normalize_token_distribution()

        elapsed = time.time() - start
        trace_logger.info(f"✅ Thread-{thread_id} extracted {source} in {elapsed:.2f}s")
        update_index_progress(
            stage="processing_documents",
            current_file=source,
            file_details={"documentPhase": "Waiting to save"},
        )
        return {
            "source": source,
            "state": ingested_state,
            "token_utils": ingest_token_utils,
            "chunker": ingest_chunker,
        }
    except Exception as exc:
        trace_logger.error(f"❌ Error processing {source}: {exc}")
        raise
    finally:
        finish_document_worker()


def persist_incremental_document(extracted, current_manifest):
    source = extracted["source"]
    ingested_state = extracted["state"]
    ingest_chunker = extracted["chunker"]

    raw_chunk_counts = count_ingest_chunks_by_document(ingested_state, vector_store=vector_store)
    raw_image_counts = count_ingest_images_by_document(
        ingested_state.get_image_store().keys(),
        [source],
        image_asset_belongs_to_document=image_asset_belongs_to_document,
    )
    raw_ocr_image_counts = count_ingest_images_by_document(
        ingested_state.get_image_page_text().keys(),
        [source],
        image_asset_belongs_to_document=image_asset_belongs_to_document,
    )
    update_index_progress(
        current_file=source,
        file_details={
            "documentPhase": "Embedding text",
            "rawChunks": sum(raw_chunk_counts.values()),
            "extractedImages": sum(raw_image_counts.values()),
            "ocrImageTexts": sum(raw_ocr_image_counts.values()),
        },
    )
    builder = IndexBuilder(ingested_state, ingest_chunker, embedder, config, trace_logger, batch_size_resolver=effective_embedding_batch_size)
    build_result = builder.build()
    update_index_progress(
        current_file=source,
        file_details={
            "documentPhase": "Saving text chunks",
            "chunks": build_result.chunks,
            "droppedChunks": build_result.dropped_chunks,
            "indexedImageTexts": build_result.images,
        },
    )
    document_stats = collect_ingest_stats(
        ingested_state,
        [source],
        vector_store=vector_store,
        image_asset_belongs_to_document=image_asset_belongs_to_document,
        raw_chunk_counts=raw_chunk_counts,
        raw_image_counts=raw_image_counts,
        raw_ocr_image_counts=raw_ocr_image_counts,
    )
    vector_store.replace_sources(
        delete_rel_paths=[source],
        file_records=current_manifest,
        chunks=ingested_state.get_chunks(),
        sources=ingested_state.get_sources(),
        metadata=ingested_state.get_metadata(),
        embeddings=np.asarray(ingested_state.get_embeddings(), dtype="float32"),
        status="pending",
        document_stats=document_stats,
    )
    update_index_progress(
        current_file=source,
        file_details={
            "documentPhase": "Saving images",
            "extractedImages": sum(raw_image_counts.values()),
            "indexedImageTexts": build_result.images,
        },
    )
    image_result = persist_db_image_state(
        current_manifest,
        target_state=ingested_state,
        rel_paths=[source],
        progress_file=source,
    )
    mark_source_ready_for_review(source)
    ai_review = maybe_review_ingestion_with_openai(source, ingested_state, document_stats)
    final_details = {
        **summarize_document_ingest_stats(document_stats),
        **image_result,
    }
    if ai_review:
        final_details["aiIngestionReviews"] = 1
        final_details["aiIngestionReviewPaidBy"] = ai_review.get("paidBy")
    update_index_progress(
        stage="processing_documents",
        finished_file=source,
        details={**final_details, "lastCompletedDocument": source},
    )
    trace_logger.info(f"✅ {source} is ready for review.")
    return build_result, final_details


def mark_source_ready_for_review(source):
    ready_sources = vector_store.set_sources_status([source], "needs_review")
    if source not in ready_sources:
        raise RuntimeError(f"{source} could not be marked ready for review.")
    return ready_sources


def run_incremental_ingest(changes, current_manifest):
    if changes.removed:
        trace_logger.info(
            f"📚 Ignoring {len(changes.removed)} missing training files because the DB catalog is authoritative. "
            "Use Admin Remove to delete documents from CircuitShelf."
        )
    delete_rel_paths = changes.modified
    changed_rel_paths = changes.changed_or_added

    trace_logger.info(
        f"🔁 Incremental ingest. Added: {len(changes.added)}, modified: {len(changes.modified)}, "
        f"removed: {len(changes.removed)}"
    )
    prune_training_files_from_state(delete_rel_paths)

    total_chunks = 0
    total_dropped_chunks = 0
    total_images = 0
    embedding_dim = 0
    failed_files = []
    aggregate_details = {
        "rawChunks": 0,
        "chunks": 0,
        "droppedChunks": 0,
        "extractedImages": 0,
        "indexedImageTexts": 0,
        "ocrImageTexts": 0,
        "storedImages": 0,
        "skippedImages": 0,
    }
    final_details = {}
    if changed_rel_paths:
        cpu_count = detected_cpu_count()
        max_workers = document_worker_count(len(changed_rel_paths), cpu_count=cpu_count)
        trace_logger.info(
            f"⚙️ Ingest worker budget: {cpu_count} cores detected, reserving {reserved_core_count(cpu_count)}, "
            f"{usable_core_count(cpu_count)} usable, {max_workers} document workers for {len(changed_rel_paths)} files."
        )
        update_index_progress(
            stage="processing_documents",
            total_files=len(changed_rel_paths),
            details={
                "documents": len(changed_rel_paths),
                "activeWorkers": max_workers,
            },
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(extract_document_for_incremental_ingest, source): source
                for source in changed_rel_paths
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    extracted = future.result()
                    build_result, document_details = persist_incremental_document(extracted, current_manifest)
                    total_chunks += build_result.chunks
                    total_dropped_chunks += build_result.dropped_chunks
                    total_images += build_result.images
                    embedding_dim = build_result.embedding_dim
                    for key in aggregate_details:
                        aggregate_details[key] += int(document_details.get(key, 0) or 0)
                    final_details = {
                        "documents": len(changed_rel_paths),
                        "completedDocuments": int(index_status.get("processedFiles") or 0),
                        **aggregate_details,
                        "failedDocuments": len(failed_files),
                    }
                    update_index_detail(**final_details)
                except ValueError as exc:
                    failed_files.append(source)
                    trace_logger.warning(f"⚠️ {source} produced no valid chunks: {exc}")
                    vector_store.delete_sources([source])
                    update_index_progress(
                        stage="processing_documents",
                        finished_file=source,
                        details={
                            "documents": len(changed_rel_paths),
                            "failedDocuments": len(failed_files),
                            "failedFiles": failed_files[:10],
                        },
                    )
                except Exception as exc:
                    failed_files.append(source)
                    trace_logger.error(f"❌ Incremental document ingest failed for {source}: {exc}")
                    update_index_progress(
                        stage="processing_documents",
                        finished_file=source,
                        details={
                            "documents": len(changed_rel_paths),
                            "failedDocuments": len(failed_files),
                            "failedFiles": failed_files[:10],
                        },
                    )

        final_details = {
            **final_details,
            "documents": len(changed_rel_paths),
            "completedDocuments": len(changed_rel_paths) - len(failed_files),
            **aggregate_details,
            "failedDocuments": len(failed_files),
        }
    elif delete_rel_paths:
        vector_store.delete_sources(delete_rel_paths)

    build_result = None
    if total_chunks:
        build_result = IndexBuildResult(
            chunks=total_chunks,
            dropped_chunks=total_dropped_chunks,
            images=total_images,
            embedding_dim=embedding_dim,
        )
    return build_result, final_details


def reindex_review_source(source):
    manifest = build_ingest_manifest()
    current_manifest = manifest.scan()
    if source not in current_manifest:
        raise FileNotFoundError(f"Training file not found: {source}")

    prune_training_files_from_state([source])
    ingested_state, ingest_token_utils, ingest_chunker = build_ingest_context()
    load_documents_parallel(
        folder=TRAINING_DIR,
        files_selected=[source],
        clear_existing=True,
        target_state=ingested_state,
        target_chunker=ingest_chunker,
        target_token_utils=ingest_token_utils,
        progress_callback=update_index_progress,
    )
    raw_chunk_counts = count_ingest_chunks_by_document(ingested_state, vector_store=vector_store)
    raw_image_counts = count_ingest_images_by_document(
        ingested_state.get_image_store().keys(),
        [source],
        image_asset_belongs_to_document=image_asset_belongs_to_document,
    )
    raw_ocr_image_counts = count_ingest_images_by_document(
        ingested_state.get_image_page_text().keys(),
        [source],
        image_asset_belongs_to_document=image_asset_belongs_to_document,
    )
    update_index_progress(
        stage="embedding_chunks",
        details={
            "documents": 1,
            "rawChunks": sum(raw_chunk_counts.values()),
            "extractedImages": sum(raw_image_counts.values()),
            "ocrImageTexts": sum(raw_ocr_image_counts.values()),
        },
    )
    builder = IndexBuilder(ingested_state, ingest_chunker, embedder, config, trace_logger, batch_size_resolver=effective_embedding_batch_size)
    build_result = builder.build()
    update_index_progress(
        stage="persisting_chunks",
        details={
            "documents": 1,
            "chunks": build_result.chunks,
            "droppedChunks": build_result.dropped_chunks,
            "extractedImages": sum(raw_image_counts.values()),
            "indexedImageTexts": build_result.images,
            "ocrImageTexts": sum(raw_ocr_image_counts.values()),
        },
    )
    document_stats = collect_ingest_stats(
        ingested_state,
        [source],
        vector_store=vector_store,
        image_asset_belongs_to_document=image_asset_belongs_to_document,
        raw_chunk_counts=raw_chunk_counts,
        raw_image_counts=raw_image_counts,
        raw_ocr_image_counts=raw_ocr_image_counts,
    )
    vector_store.replace_sources(
        delete_rel_paths=[source],
        file_records=current_manifest,
        chunks=ingested_state.get_chunks(),
        sources=ingested_state.get_sources(),
        metadata=ingested_state.get_metadata(),
        embeddings=np.asarray(ingested_state.get_embeddings(), dtype="float32"),
        status="pending",
        document_stats=document_stats,
    )
    update_index_progress(
        stage="persisting_images",
        details={
            "documents": 1,
            "chunks": build_result.chunks,
            "droppedChunks": build_result.dropped_chunks,
            "extractedImages": sum(raw_image_counts.values()),
            "indexedImageTexts": build_result.images,
        },
    )
    image_result = persist_db_image_state(current_manifest, target_state=ingested_state, rel_paths=[source])
    update_index_progress(stage="readying_review", details={**summarize_document_ingest_stats(document_stats), **image_result})
    mark_source_ready_for_review(source)
    maybe_review_ingestion_with_openai(source, ingested_state, document_stats)
    return build_result


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
        with INDEX_PROGRESS_LOCK:
            detail_snapshot = dict(index_status.get("details") or {})
            last_changes = index_status.get("lastChanges")
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



