# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 06:54:37 2025

@author: sueco, rew
"""


# ===  Imports, Logging, and Configuration ===

import os
import re
import requests
import time
import base64
import zipfile
import uuid
import tempfile
import fitz  # PyMuPDF
import pytesseract
import nltk
import numpy as np
import pandas as pd
import threading
import uvicorn
import nltk
import bench_tools
from lxml import etree
from datetime import datetime, timezone
from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from collections import deque, OrderedDict
from contextlib import asynccontextmanager
from docx import Document
from sentence_transformers import SentenceTransformer, CrossEncoder
from io import BytesIO
from PIL import Image
from nltk.tokenize import sent_tokenize
from requests.exceptions import RequestException
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles



#internal
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
from datasheet_intelligence import build_datasheet_intelligence
from circuit_build_cards import (
    RECOVERY_SYSTEM_PROMPT,
    build_circuit_build_card,
    build_recovery_prompt,
    parse_recovered_build_card,
)
from response_finalizer import RESPONSE_FINALIZER_SYSTEM_PROMPT, finalize_response
from ingest_manifest import IngestManifest
from ingest_workers import detected_cpu_count, document_worker_count, ocr_worker_count, reserved_core_count, usable_core_count
from log_tail import tail_text_file
from log_retention import cleanup_old_logs
from conversation_manager import append_chat_turn, build_chat_messages, build_contextual_retrieval_query
from db.connection import Database, database_url_from_config
from db.assembly_plan_store import AssemblyPlanStore
from db.conversation_store import ConversationStore
from db.datasheet_intelligence_store import DatasheetIntelligenceStore
from db.image_store import ImageStore
from db.lab_inventory import LabInventoryStore, ProjectFinderStore
from db.query_log_store import QueryLogStore
from db.response_cache_store import PostgresResponseCache
from db.runtime_config_store import RuntimeConfigStore
from db.settings import AppSettingsStore
from db.user_preferences import UserPreferencesStore
from db.users import UserStore
from db.vector_store import VectorStore
from process_lock import ProcessLockError, acquire_process_lock
from response_cache import (
    ResponseCacheEntry,
    ResponseCacheKey,
    should_cache_response,
)
from settings_runtime import RuntimeSettingsManager

#Inits the logger as well as the configuraqtion system
config, trace_logger = SystemInit.load_config_and_logger()
state = StateManager(use_lock=True, cache_capacity=200, trace_logger=trace_logger)
database = Database(database_url_from_config(config), trace_logger)
if not database.configured:
    raise RuntimeError("DATABASE_URL is required. CircuitShelf is database-backed and no longer supports file-backed runtime state.")

settings_store = AppSettingsStore(database, trace_logger)
seeded_settings = settings_store.seed_from_config(config.config)
prompt_seeded = 0
prompt_files = {
    "PROMPT_TEMPLATE_GENERAL": os.path.join(config.get("PROMPT_DIR", "prompts"), "general_prompt.txt"),
    "PROMPT_TEMPLATE_MATH": os.path.join(config.get("PROMPT_DIR", "prompts"), "math_prompt.txt"),
}
for prompt_key, prompt_path in prompt_files.items():
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as prompt_file:
            if settings_store.seed_text_setting(prompt_key, prompt_file.read(), f"Imported from {prompt_path}."):
                prompt_seeded += 1
settings_store.seed_setting("STATUS_POLL_INTERVAL_SECONDS", 15, "Browser status refresh interval while indexing is idle.")
settings_store.seed_setting("STATUS_POLL_ACTIVE_INTERVAL_SECONDS", 3, "Browser status refresh interval while indexing is running.")
settings_store.seed_setting("SESSION_TIMEOUT_SECONDS", 28800, "Seconds of idle time before a browser login session expires.")
settings_store.seed_setting("INGEST_WATCH_INTERVAL_SECONDS", 300, "Seconds between automatic document-change checks.")
settings_store.seed_setting("LOG_RETENTION_DAYS", 14, "Days to keep trace log files. Set to 0 to disable automatic cleanup.")
settings_store.seed_setting("PDF_RENDER_VECTOR_PAGES", True, "Render vector-heavy PDF pages as searchable images.")
settings_store.seed_setting("PDF_RENDER_MAX_PAGES_PER_DOC", 8, "Maximum rendered visual PDF pages stored per document.")
settings_store.seed_setting("PDF_RENDER_MIN_DRAWINGS", 100, "Minimum vector drawing count before a PDF page is considered visual.")
settings_store.seed_setting("PDF_RENDER_ZOOM", 1.5, "Scale used when rendering visual PDF pages.")
settings_store.seed_setting("PDF_RENDER_RASTER_PAGES", True, "Render raster-heavy scanned PDF pages as searchable images.")
settings_store.seed_setting("PDF_RENDER_MIN_RASTER_COVERAGE", 0.8, "Minimum page image coverage before a PDF page is considered raster-heavy.")
settings_store.seed_setting("RESPONSE_FINALIZER_ENABLED", True, "Run a second model pass to validate and clean up generated answers.")
settings_store.seed_setting("RESPONSE_FINALIZER_MODE", "always", "When to run answer validation: off, always, issues, build, build_or_issues, low_confidence, or build_or_low_confidence.")
settings_store.seed_setting("RESPONSE_FINALIZER_MIN_CONFIDENCE", 0.80, "Retrieval confidence threshold used by low-confidence finalizer modes.")
settings_store.seed_setting("RESPONSE_FINALIZER_MAX_CONTEXT_CHARS", 7000, "Maximum source-summary characters sent to the response finalizer.")
applied_settings = settings_store.apply_to_config(config)
runtime_config_store = RuntimeConfigStore(database, trace_logger)
seeded_runtime_config = runtime_config_store.seed_from_config(config.config)
applied_runtime_config = runtime_config_store.apply_to_config(config)
if seeded_settings or applied_settings or seeded_runtime_config or applied_runtime_config:
    trace_logger.info(
        f"⚙️ DB settings active. Seeded: {seeded_settings}, "
        f"prompts: {prompt_seeded}, loaded: {applied_settings}, "
        f"runtime seeded: {seeded_runtime_config}, runtime tables: {sorted(applied_runtime_config.keys())}"
    )
user_store = UserStore(database, trace_logger)
user_preferences_store = UserPreferencesStore(database, trace_logger)
query_log_store = QueryLogStore(database, trace_logger)
conversation_store = ConversationStore(database, trace_logger)
vector_store = VectorStore(database, config.get("TRAINING_DIR", "training"), config.get("EMBED_MODEL_NAME"), trace_logger)
image_store = ImageStore(database, config.get("TRAINING_DIR", "training"), trace_logger)
intelligence_store = DatasheetIntelligenceStore(database, trace_logger)
assembly_plan_store = AssemblyPlanStore(database, config.get("TRAINING_DIR", "training"), trace_logger)
lab_inventory_store = LabInventoryStore(database, trace_logger)
project_finder_store = ProjectFinderStore(database, lab_inventory_store, trace_logger)
db_response_cache = PostgresResponseCache(
    database,
    capacity=config.get("RESPONSE_CACHE_CAPACITY", 200),
    logger=trace_logger,
)
if not vector_store.available():
    raise RuntimeError("Postgres vector store is unavailable. Run database migrations before starting CircuitShelf.")
if not image_store.available():
    raise RuntimeError("Postgres image store is unavailable. Run database migrations before starting CircuitShelf.")
if not intelligence_store.available():
    raise RuntimeError("Postgres datasheet intelligence store is unavailable. Run database migrations before starting CircuitShelf.")
if not db_response_cache.available():
    raise RuntimeError("Postgres response cache is unavailable. Run database migrations before starting CircuitShelf.")
if not query_log_store.available():
    raise RuntimeError("Postgres query log is unavailable. Run database migrations before starting CircuitShelf.")
if not conversation_store.available():
    raise RuntimeError("Postgres conversation store is unavailable. Run database migrations before starting CircuitShelf.")
if not assembly_plan_store.available():
    raise RuntimeError("Postgres assembly plan store is unavailable. Run database migrations before starting CircuitShelf.")
if not user_preferences_store.available():
    raise RuntimeError("Postgres user preferences store is unavailable. Run database migrations before starting CircuitShelf.")
if not lab_inventory_store.available():
    raise RuntimeError("Postgres lab inventory store is unavailable. Run database migrations before starting CircuitShelf.")
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




# === NLTK Data Directory HARDENED ===
# Ensure NLTK searches here first/insure it can not download 
# Check to insure the path is there or halt system.
if config.get("BYPASS_NLTK_DOWNLOAD", True):

    NLTK_DATA_DIR = config.get("NLTK_DATA_DIR")
    if os.path.exists(NLTK_DATA_DIR):
        trace_logger.info(f"NLTK_DATA_DIR '{NLTK_DATA_DIR}' exists. Using it for NLTK data.")
        # here is where we override the NLTK download info to throw a Runtime error if it tries to download
        if NLTK_DATA_DIR not in nltk.data.path:
            nltk.data.path.insert(0, NLTK_DATA_DIR)
        nltk.download = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Downloading NLTK data is disabled in production."))

    else:
        trace_logger.warning(f"NLTK_DATA_DIR '{NLTK_DATA_DIR}' does not exist. Please check falling back to Local.")

# === pytesseract path if needed Doing an OS check , only for windoooooows

if os.name == 'nt':    
    trace_logger.info("We are on Windows, Set the tesseract_cmd")
    pytesseract.pytesseract.tesseract_cmd = config.get("TESSERACT_CMD",r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe")


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

reranker_engine = Reranker(config, state, chunker, trace_logger)
runtime_settings.register_callback("RERANK_PROFILES", lambda value: setattr(reranker_engine, "rerank_profiles", value))
query_timings = deque(maxlen=100)
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
        active_log_file=current_trace_log_file(),
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


def file_changes_payload(changes):
    if not changes:
        return None
    return {
        "added": len(changes.added),
        "modified": len(changes.modified),
        "removed": len(changes.removed),
        "unchanged": len(changes.unchanged),
        "addedFiles": changes.added[:20],
        "modifiedFiles": changes.modified[:20],
        "removedFiles": changes.removed[:20],
        "unchangedFiles": changes.unchanged[:20],
    }


def count_state_chunks_by_document(target_state):
    counts = {}
    sources = target_state.get_sources()
    metadata = target_state.get_metadata()
    for idx, source in enumerate(sources):
        meta = metadata[idx] if idx < len(metadata) else {}
        rel_path = vector_store.rel_path_for_source(source, meta)
        counts[rel_path] = counts.get(rel_path, 0) + 1
    return counts


def count_state_images_by_document(image_keys, rel_paths):
    counts = {rel_path: 0 for rel_path in rel_paths}
    for image_id in image_keys:
        for rel_path in rel_paths:
            if image_asset_belongs_to_document(image_id, rel_path):
                counts[rel_path] += 1
                break
    return counts


def collect_document_ingest_stats(target_state, rel_paths, raw_chunk_counts=None, raw_image_counts=None, raw_ocr_image_counts=None):
    rel_paths = list(rel_paths or [])
    kept_chunk_counts = count_state_chunks_by_document(target_state)
    indexed_image_counts = count_state_images_by_document(target_state.get_image_id_list(), rel_paths)
    raw_chunk_counts = raw_chunk_counts or {}
    raw_image_counts = raw_image_counts or count_state_images_by_document(target_state.get_image_store().keys(), rel_paths)
    raw_ocr_image_counts = raw_ocr_image_counts or count_state_images_by_document(target_state.get_image_page_text().keys(), rel_paths)

    stats = {}
    for rel_path in rel_paths:
        raw_chunks = int(raw_chunk_counts.get(rel_path, 0) or 0)
        kept_chunks = int(kept_chunk_counts.get(rel_path, 0) or 0)
        stats[rel_path] = {
            "rawChunkCount": raw_chunks,
            "chunkCount": kept_chunks,
            "droppedChunkCount": max(raw_chunks - kept_chunks, 0),
            "extractedImageCount": int(raw_image_counts.get(rel_path, 0) or 0),
            "indexedImageTextCount": int(indexed_image_counts.get(rel_path, 0) or 0),
            "ocrImageTextCount": int(raw_ocr_image_counts.get(rel_path, 0) or 0),
        }
    return stats


def summarize_document_ingest_stats(document_stats):
    values = list((document_stats or {}).values())
    return {
        "documents": len(values),
        "rawChunks": sum(item.get("rawChunkCount", 0) for item in values),
        "chunks": sum(item.get("chunkCount", 0) for item in values),
        "droppedChunks": sum(item.get("droppedChunkCount", 0) for item in values),
        "extractedImages": sum(item.get("extractedImageCount", 0) for item in values),
        "indexedImageTexts": sum(item.get("indexedImageTextCount", 0) for item in values),
        "ocrImageTexts": sum(item.get("ocrImageTextCount", 0) for item in values),
    }


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
    builder = IndexBuilder(state, chunker, embedder, config, trace_logger)
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
            batch_size=config.get("EMBED_BATCH_SIZE", 32),
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
        batch_size=config.get("EMBED_BATCH_SIZE", 32),
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

    raw_chunk_counts = count_state_chunks_by_document(ingested_state)
    raw_image_counts = count_state_images_by_document(ingested_state.get_image_store().keys(), [source])
    raw_ocr_image_counts = count_state_images_by_document(ingested_state.get_image_page_text().keys(), [source])
    update_index_progress(
        current_file=source,
        file_details={
            "documentPhase": "Embedding text",
            "rawChunks": sum(raw_chunk_counts.values()),
            "extractedImages": sum(raw_image_counts.values()),
            "ocrImageTexts": sum(raw_ocr_image_counts.values()),
        },
    )
    builder = IndexBuilder(ingested_state, ingest_chunker, embedder, config, trace_logger)
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
    document_stats = collect_document_ingest_stats(
        ingested_state,
        [source],
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
    final_details = {
        **summarize_document_ingest_stats(document_stats),
        **image_result,
    }
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
    raw_chunk_counts = count_state_chunks_by_document(ingested_state)
    raw_image_counts = count_state_images_by_document(ingested_state.get_image_store().keys(), [source])
    raw_ocr_image_counts = count_state_images_by_document(ingested_state.get_image_page_text().keys(), [source])
    update_index_progress(
        stage="embedding_chunks",
        details={
            "documents": 1,
            "rawChunks": sum(raw_chunk_counts.values()),
            "extractedImages": sum(raw_image_counts.values()),
            "ocrImageTexts": sum(raw_ocr_image_counts.values()),
        },
    )
    builder = IndexBuilder(ingested_state, ingest_chunker, embedder, config, trace_logger)
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
    document_stats = collect_document_ingest_stats(
        ingested_state,
        [source],
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
    return build_result


def check_for_training_changes(reason="watch"):
    if not INDEX_JOB_LOCK.acquire(blocking=False):
        trace_logger.info(f"⏳ Index check skipped for {reason}; another index job is running.")
        return set_index_status(lastResult="already_running")

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
        elif changes.removed and not changes.changed_or_added:
            result = f"ignored {len(changes.removed)} missing source files"
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


@trace_timer("search_top_images")
def search_top_images(question, top_n=4):
    action_keywords = ["click", "enter", "select", "choose", "screen", "dashboard", "button", "setting"]
    query_emb = embedder.encode([question], convert_to_numpy=True).astype("float32")
    results = []

    for row in image_store.search_images(query_emb[0], top_k=top_n * 2):
        img_id = row["image_key"]
        score_boost = 0.0
        ocr_text = str(row.get("ocr_text") or "").lower()
        if any(kw in ocr_text for kw in action_keywords):
            score_boost += 0.05
        results.append((img_id, float(row["distance"]) - score_boost))

    return sorted(results, key=lambda x: x[1])[:top_n]




# === Query Normalization and Expansion ===
def normalize_question(q):
    
    wrkStr = sanitize_input(q)
    return re.sub(r"\s+", " ", wrkStr.strip().lower())




def expand_query(q):

    synonym_pairs = config.get("QUERY_SYNONYMS", [])
    synonyms = set()
    q_lower = str(q).lower()

    for pair in synonym_pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            trace_logger.warning(f"⚠️ Invalid QUERY_SYNONYMS entry skipped: {pair!r}")
            continue
        orig, repl = (str(pair[0]).lower(), str(pair[1]).lower())
        if orig in q_lower:
            synonyms.add(q_lower.replace(orig, repl))

    synonyms.add(q_lower)
    return list(OrderedDict.fromkeys(synonyms))


def document_source_from_metadata(source, metadata=None):
    metadata = metadata or {}
    return metadata.get("parent_source") or metadata.get("source") or source


def display_source_name(source):
    return os.path.basename(source) if source else "Unknown"


def source_image_id_from_metadata(source, metadata=None):
    metadata = metadata or {}
    if metadata.get("source_image_id"):
        return metadata["source_image_id"]

    candidate = metadata.get("source") or source
    if not candidate:
        return None

    candidate_base = os.path.basename(candidate)
    parent_base = os.path.basename(metadata.get("parent_source") or "")
    if parent_base and candidate_base.startswith(f"{parent_base}_page"):
        return candidate
    if "_page" in candidate_base and "_img" in candidate_base:
        return candidate
    return None


def image_asset_belongs_to_document(image_id, doc_source):
    doc_base = os.path.basename(doc_source or "")
    if not doc_base:
        return False
    return (
        image_id == doc_base
        or image_id.startswith(f"{doc_base}_page")
        or image_id.startswith(f"{doc_base}_textbox")
    )


def image_asset_count_for_document(doc_source):
    return sum(
        1
        for image_id in state.get_image_store().keys()
        if image_asset_belongs_to_document(image_id, doc_source)
    )


def deduplicate_hits_by_index(hits):
    best_by_index = {}
    for idx, distance in hits:
        if idx not in best_by_index or distance < best_by_index[idx]:
            best_by_index[idx] = distance
    return sorted(best_by_index.items(), key=lambda item: item[1])


def build_db_chunk_index():
    mapping = {}
    per_source_counts = {}
    metadata = state.get_metadata()
    sources = state.get_sources()
    for idx, source in enumerate(sources):
        meta = metadata[idx] if idx < len(metadata) else {}
        rel_path = meta.get("db_source_path") or vector_store.rel_path_for_source(source, meta)
        chunk_index = meta.get("db_chunk_index")
        if chunk_index is None:
            chunk_index = per_source_counts.get(rel_path, 0)
        per_source_counts[rel_path] = int(chunk_index) + 1
        mapping[(rel_path, int(chunk_index))] = idx
    return mapping


def vector_results_to_hits(results):
    index_by_key = build_db_chunk_index()
    hits = []
    for result in results:
        rel_path = vector_store.rel_path_for_source(result.get("source", ""), {})
        key = (rel_path, int(result.get("chunk_index", 0)))
        idx = index_by_key.get(key)
        if idx is None:
            trace_logger.warning(f"⚠️ Retrieved DB chunk not found in runtime state: {key}")
            continue
        hits.append((idx, float(result.get("distance", 0.0))))
    return hits


#def clean_response(text):
#    return re.sub(r"<[^>]+>", "", text).strip()



#Prompt file processing        
@trace_timer("load_prompt_template")
def load_prompt_template(path: str, context: str, question: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            template = f.read()
        return template.format(context=context, question=question)
    except Exception as e:
        trace_logger.error(f"❌ Failed to load prompt template {path}: {e}")
        return f"[Prompt load error: {e}]"

def build_prompt(context: str, question: str, is_math: bool = False) -> str:
    db_template_key = "PROMPT_TEMPLATE_MATH" if is_math else "PROMPT_TEMPLATE_GENERAL"
    db_template = config.get(db_template_key)
    if db_template:
        try:
            return db_template.format(context=context, question=question)
        except Exception as e:
            trace_logger.error(f"❌ Failed to format DB prompt template {db_template_key}: {e}")

    prompt_file = os.path.join(PROMPT_DIR, "math_prompt.txt" if is_math else "general_prompt.txt")

    return load_prompt_template(prompt_file, context, question)


def trim_chunks_to_token_budget(selected_chunks, max_tokens):
    if not max_tokens:
        return selected_chunks

    trimmed = []
    token_total = 0
    for chunk in selected_chunks:
        chunk_tokens = TokenUtils.tokenize_len(chunk.get("text", ""))
        if trimmed and token_total + chunk_tokens > max_tokens:
            break
        trimmed.append(chunk)
        token_total += chunk_tokens

    return trimmed

def get_average_query_time():
    if not query_timings:
        return "N/A"
    avg_time = sum(query_timings) / len(query_timings)
    return f"{avg_time:.2f} sec over {len(query_timings)} queries"


@trace_timer("query_ollama_chat with retry")
def query_ollama_chat_with_retry(prompt, model_name, chat_history=None, retries=None, delay=None, system_prompt=None):
    retries = int(QUERY_RETRIES if retries is None else retries)
    delay = float(QUERY_RETRY_DELAY if delay is None else delay)

    LLM_API_KEY = config.get("LLM_API_KEY", "")
    url = f"{OLLAMA_API_URL}/chat"

    headers = {
        "Content-Type": "application/json"
    }
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    options = {
        "temperature": float(LLM_TEMPERATURE),
        "num_predict": int(LLM_NUM_PREDICT),
    }
    if LLM_NUM_CTX:
        options["num_ctx"] = int(LLM_NUM_CTX)

    payload = {
        "model": model_name or "default",
        "stream": False,
        "messages": build_chat_messages(
            system_prompt or RAG_CHAT_SYSTEM_PROMPT,
            prompt,
            chat_history,
            max_turns=MAX_CHAT_HISTORY_TURNS,
            max_chars=MAX_CHAT_HISTORY_CHARS,
        ),
        "options": options,
    }

    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=POST_TIMEOUT)
            response.raise_for_status()

            json_data = response.json() #CLEAN THIS UP LATER
            result = json_data.get("message", {}).get("content", "").strip()
            done_reason = json_data.get("done_reason", "")
            if done_reason in {"length", "max_tokens"}:
                trace_logger.warning(
                    "⚠️ Ollama response stopped at generation limit. "
                    f"Increase LLM_NUM_PREDICT above {LLM_NUM_PREDICT} if this answer needs more room."
                )
                result = (
                    f"{result}\n\n"
                    "> Response stopped at the model generation limit. "
                    "Increase the answer token limit and ask again if this is incomplete."
                )

            trace_logger.debug(f"✅ LLM call success: {result[:80]}...")
            return result

        except RequestException as ex:
            trace_logger.warning(f"⚠️ LLM call failed (attempt {attempt+1}/{retries}) | {ex}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                return "[LLM error]"




def sanitize_input(user_input: str) -> str:
    
    for phrase in BANNED_PHRASES:
        user_input = re.sub(phrase, "[REDACTED]", user_input, flags=re.IGNORECASE)
    return user_input


@trace_timer("get_rag_response")
def get_rag_response(
    question,
    chat_history,
    show_full_text=True,
    top_k=15,
    dist_thresh=4.0,
    max_tokens=1800,
    bypass_cache=True,
    strategy="Vector + CrossEncoder",
    model_name=None,
    user_id=None,
    username=None,
):
    start_time = time.time()
    model_name = model_name or (LLM_MODEL_OPTIONS[0] if LLM_MODEL_OPTIONS else LLM_MODEL_NAME)
    norm_q = normalize_question(question)
    retrieval_q = normalize_question(build_contextual_retrieval_query(norm_q, chat_history))
    synonyms = expand_query(retrieval_q)
    cache_enabled = should_cache_response(chat_history, bypass_cache)
    response_cache = get_response_cache()
    cache_key = build_response_cache_key(
        model_name=model_name,
        strategy=strategy,
        norm_q=norm_q,
        retrieval_q=retrieval_q,
        top_k=top_k,
        dist_thresh=dist_thresh,
        max_tokens=max_tokens,
        show_full_text=show_full_text,
    )

    if cache_enabled:
        cached = response_cache.get_response(cache_key)
        if cached:
            trace_logger.info(f"✅ Response cache HIT: {cache_key.digest()}")
            query_timings.append(time.time() - start_time)
            chat_history = [list(turn) for turn in cached.chat_history]
            confidence = cached.confidence
            query_log_store.log_query(
                model_name=model_name,
                retrieval_strategy=strategy,
                question=norm_q,
                retrieval_query=retrieval_q,
                elapsed_ms=int((time.time() - start_time) * 1000),
                cache_hit=True,
                confidence_score=confidence,
                selected_chunks=[],
                user_id=user_id,
                username=username,
            )
            build_card = build_circuit_build_card(
                norm_q,
                cached.sources,
                intelligence_for_question_and_sources(retrieval_q, cached.sources),
                context_question=retrieval_q,
            )
            return norm_q, cached.answer, chat_history, cached.sources, response_cache.stats(), confidence, get_average_query_time(), build_card, None
    else:
        if bypass_cache:
            trace_logger.debug("Response cache bypassed by request option.")
        elif chat_history:
            trace_logger.debug("Response cache skipped for conversational request.")

    trace_logger.info(f"🔍 Response cache MISS: {cache_key.digest()} | Executing query")

    if not cache_enabled:
        response_cache.misses += 1

    all_hits = []
    vector_start = time.time()
    for syn in synonyms:
        emb = embedder.encode([syn], convert_to_numpy=True).astype("float32")
        vector_results = vector_store.search_chunks(emb[0], top_k=top_k)
        for i, dist in vector_results_to_hits(vector_results):
            adjusted = dist * (1 + 0.1 * (1 - len(state.chunks[i]) / 500))
            if adjusted < dist_thresh:
                all_hits.append((i, adjusted))
    vector_duration = time.time() - vector_start

    if not all_hits:
        response = f"No relevant documents found for: {norm_q}"
        trace_logger.warning(f"⚠️ No results for query: {norm_q}")
        chat_history = append_chat_turn(
            chat_history,
            norm_q,
            response,
            max_turns=MAX_CHAT_HISTORY_TURNS,
            max_chars=MAX_CHAT_HISTORY_CHARS,
        )
        return norm_q, response, chat_history, [], response_cache.stats(), "0.00", get_average_query_time(), None, None

    dedup_hits = deduplicate_hits_by_index(all_hits)
    rerank_duration = None

    if strategy == "Vector only":
        selected = sorted(dedup_hits, key=lambda x: x[1])[:top_k]
        selected_chunks = reranker_engine.build_chunk_payload(selected)
        confidence = chunker.compute_vector_confidence(selected, dist_thresh)
        profile = "N/A"
    else:
        rerank_start = time.time()
        reranked_chunks, confidence, profile = reranker_engine.rerank_chunks(dedup_hits, retrieval_q)
        rerank_duration = time.time() - rerank_start
        selected_chunks = reranked_chunks
        if not selected_chunks:
            trace_logger.warning("⚠️ Reranker returned no chunks; falling back to top vector hits.")
            selected = sorted(dedup_hits, key=lambda x: x[1])[:top_k]
            selected_chunks = reranker_engine.build_chunk_payload(selected)
            confidence = chunker.compute_vector_confidence(selected, dist_thresh)
            profile = f"{profile} (vector fallback)"

    selected_chunks = trim_chunks_to_token_budget(selected_chunks, max_tokens)

    # === Build Final Prompt
    context = "\n\n".join([c["text"] for c in selected_chunks])
    prompt = build_prompt(context, norm_q, chunker.is_math_heavy_question(norm_q))

    source_payload = build_source_payload(selected_chunks)

    # === LLM Call
    response = query_ollama_chat_with_retry(prompt, model_name, chat_history=chat_history)

    build_card = build_circuit_build_card(
        norm_q,
        source_payload,
        intelligence_for_question_and_sources(retrieval_q, source_payload),
        context_question=retrieval_q,
    )
    revised_response, validation = finalize_response(
        question=norm_q,
        answer=response,
        source_payload=source_payload,
        build_card=build_card,
        model_name=model_name,
        confidence=confidence,
        enabled=RESPONSE_FINALIZER_ENABLED,
        mode=RESPONSE_FINALIZER_MODE,
        min_confidence=RESPONSE_FINALIZER_MIN_CONFIDENCE,
        max_context_chars=RESPONSE_FINALIZER_MAX_CONTEXT_CHARS,
        llm_call=lambda finalizer_prompt: query_ollama_chat_with_retry(
            finalizer_prompt,
            model_name,
            [],
            system_prompt=RESPONSE_FINALIZER_SYSTEM_PROMPT,
        ),
    )

    # === Format Output
    image_md_blocks = build_image_markdown_blocks(retrieval_q, selected_chunks) if show_full_text else []
    final_answer = _assemble_final_markdown(revised_response, image_md_blocks)

    chat_history = append_chat_turn(
        chat_history,
        norm_q,
        revised_response,
        max_turns=MAX_CHAT_HISTORY_TURNS,
        max_chars=MAX_CHAT_HISTORY_CHARS,
    )
    if cache_enabled:
        response_cache.put_response(
            cache_key,
            ResponseCacheEntry(
                answer=final_answer,
                chat_history=[list(turn) for turn in chat_history],
                sources=source_payload,
                confidence=confidence,
                metadata={
                    "model": model_name,
                    "strategy": strategy,
                    "retrieval_query": retrieval_q,
                },
            ),
        )
    query_timings.append(time.time() - start_time)

    state.update_last_trace({
        "question": norm_q,
        "retrieval_query": retrieval_q,
        "strategy": strategy,
        "model": model_name,
        "confidence": confidence,
        "weighting_profile": profile,
        "vector_duration": f"{vector_duration:.2f}s",
        "rerank_duration": "N/A" if rerank_duration is None else f"{rerank_duration:.2f}s",
        "finalizer": validation.api_payload() if validation else None,
        "total_duration": f"{time.time() - start_time:.2f}s",
        "top_chunks": selected_chunks,
    })

    elapsed_ms = int((time.time() - start_time) * 1000)
    query_log_store.log_query(
        model_name=model_name,
        retrieval_strategy=strategy,
        question=norm_q,
        retrieval_query=retrieval_q,
        elapsed_ms=elapsed_ms,
        cache_hit=False,
        confidence_score=confidence,
        selected_chunks=selected_chunks,
        user_id=user_id,
        username=username,
    )

    return norm_q, final_answer, chat_history, source_payload, response_cache.stats(), confidence, get_average_query_time(), build_card, validation.api_payload() if validation else None

@trace_timer("extract_doc_and_page")
def extract_doc_and_page(img_id):
    match = re.search(r"(.+?)_page(\d+)_(?:img\d+|render)$", img_id)
    if match:
        doc_name, page_str = match.groups()
        return doc_name, int(page_str)
    return img_id, -1

@trace_timer("build_image_markdown_blocks")
def build_image_markdown_blocks(question, selected_chunks=None):
    linked_images = []
    seen_images = set()
    for chunk in selected_chunks or []:
        image_id = chunk.get("source_image_id")
        if image_id and image_id not in seen_images:
            linked_images.append((image_id, -1.0))
            seen_images.add(image_id)

    matched_images = linked_images
    for img_id, score in search_top_images(question, top_n=10):
        if img_id in seen_images:
            continue
        matched_images.append((img_id, score))
        seen_images.add(img_id)
        if len(matched_images) >= 10:
            break
    
    # Group images by (doc_name, page_number)
    image_entries = []
    for img_id, _ in matched_images:
        doc_name, page = extract_doc_and_page(img_id)
        image_entries.append((doc_name, page, img_id))

    # Sort first by doc_name, then by page number
    image_entries.sort(key=lambda x: (x[0], x[1]))

    blocks = []
    current_doc = None
    image_blocks = []

    for doc_name, page, img_id in image_entries:
        if doc_name != current_doc:
            if current_doc is not None:
                blocks.append(f"""
<details style="margin-bottom: 1em;">
<summary>📄 {current_doc}</summary>
{''.join(image_blocks)}
</details>
""")
            current_doc = doc_name
            image_blocks = []

        img_data = state.image_store.get(img_id)
        mime_type = state.image_mime_types.get(img_id, "image/png")
        ocr_text = state.image_page_text.get(img_id, "")
        if not img_data:
            continue

        clean_ocr = ocr_text.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if len(clean_ocr) > 1500:
            clean_ocr = clean_ocr[:1500] + "..."
        caption = state.image_captions.get(img_id, img_id)

        image_blocks.append(f"""
<div style="margin-left: 1em;">
<details style="margin-bottom: 1em;">
<summary>📷 {caption}</summary>

<p><img src="data:{mime_type};base64,{img_data}" alt="{img_id}" style="max-width: 100%; height: auto;" /></p>

<div style="margin-left: 1.0em;">
<details>
<summary>🔍 View OCR Text</summary> 
<pre><code>{clean_ocr}</code></pre>
</details>
</div>

</details>
</div>
""")

    # Add final block
    if current_doc is not None:
        blocks.append(f"""
<details style="margin-bottom: 1em;">
<summary>📄 {current_doc}</summary>
{''.join(image_blocks)}
</details>
""")

    return blocks





def _assemble_final_markdown(response, image_blocks):
    answer_md = f"🧠 Answer\n\n{response}"  
    image_md = "🖼️ Related Images\n\n" + "\n\n".join(image_blocks) if image_blocks else ""  
    return f"{answer_md}\n\n---\n\n{image_md}" if image_md else answer_md


@asynccontextmanager
async def lifespan(_app):
    start_ingest_watcher()
    try:
        yield
    finally:
        stop_ingest_watcher()


app = FastAPI(lifespan=lifespan)


def sanitize_for_json(value):
    if isinstance(value, dict):
        return {str(key): sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return sanitize_for_json(value.tolist())
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def normalize_sources_for_api(sources):
    if isinstance(sources, str):
        return [source for source in sources.splitlines() if source.strip()]
    if isinstance(sources, (list, tuple, set)):
        return list(sources)
    return []


def api_scalar(value):
    if isinstance(value, np.generic):
        return value.item()
    return value


def build_source_payload(selected_chunks):
    grouped = OrderedDict()
    for chunk in selected_chunks:
        source = chunk.get("source") or "Unknown"
        doc = grouped.setdefault(
            source,
            {
                "source": source,
                "displayName": display_source_name(source),
                "pages": [],
                "chunkCount": 0,
                "chunks": [],
            },
        )
        page = api_scalar(chunk.get("page"))
        if page is not None and page not in doc["pages"]:
            doc["pages"].append(page)

        text = chunk.get("text", "")
        preview = re.sub(r"\s+", " ", text).strip()
        if len(preview) > 360:
            preview = f"{preview[:360].rstrip()}..."

        doc["chunkCount"] += 1
        doc["chunks"].append({
            "index": api_scalar(chunk.get("index")),
            "page": page,
            "section": chunk.get("section", "Unknown"),
            "category": chunk.get("category", "Uncategorized"),
            "distance": api_scalar(chunk.get("distance")),
            "sourceImageId": chunk.get("source_image_id"),
            "preview": preview,
        })

    for doc in grouped.values():
        doc["pages"] = sorted(doc["pages"], key=lambda item: (not isinstance(item, (int, float)), item))
    return list(grouped.values())


def document_intelligence_rel_path(source):
    return vector_store.rel_path_for_source(source or "", {})


def build_datasheet_intelligence_for_document(doc_name):
    doc_chunks = []
    doc_metadata = []
    chunks = state.get_chunks()
    metadata = state.get_metadata()
    sources = state.get_sources()

    for idx, source in enumerate(sources):
        meta = metadata[idx] if idx < len(metadata) else {}
        doc_source = document_source_from_metadata(source, meta)
        if doc_source != doc_name:
            continue
        doc_chunks.append(chunks[idx] if idx < len(chunks) else "")
        doc_metadata.append({**meta, "source": doc_name, "parent_source": doc_name})

    image_text = state.get_image_page_text()
    for image_id, text in image_text.items():
        if text and image_asset_belongs_to_document(image_id, doc_name):
            doc_chunks.append(text)
            doc_metadata.append({
                "source": doc_name,
                "parent_source": doc_name,
                "page": extract_page_number(image_id),
                "source_image_id": image_id,
            })

    return build_datasheet_intelligence(
        doc_chunks,
        doc_metadata,
        doc_name,
        display_source_name(doc_name),
    )


def stored_intelligence_is_usable(stored):
    if not stored:
        return False
    component_name = str(stored.get("componentName") or "").strip().upper()
    if component_name in {"", "LOGIC", "INPUT", "OUTPUT", "COMMON", "ABSOLUTE", "MAXIMUM"}:
        return False
    return bool(stored.get("facts") or stored.get("pinout", {}).get("pins"))


def get_or_build_datasheet_intelligence(doc_name):
    rel_path = document_intelligence_rel_path(doc_name)
    stored = intelligence_store.get_for_source(rel_path)
    if stored_intelligence_is_usable(stored):
        if not stored.get("pinout", {}).get("pins"):
            refreshed = build_datasheet_intelligence_for_document(doc_name)
            if refreshed.get("pinout", {}).get("pins"):
                intelligence_store.upsert(rel_path, refreshed)
                return refreshed
        return stored

    intelligence = build_datasheet_intelligence_for_document(doc_name)
    stored = intelligence_store.replace_for_source(rel_path, intelligence)
    if stored:
        return stored
    return intelligence


def intelligence_for_sources(source_payload):
    result = {}
    for source in source_payload or []:
        source_name = source.get("source")
        if not source_name or source_name in result:
            continue
        try:
            result[source_name] = get_or_build_datasheet_intelligence(source_name)
        except Exception as exc:
            trace_logger.warning(f"Datasheet intelligence unavailable for {source_name}: {exc}")
    return result


def question_component_terms(question):
    terms = []
    for match in re.finditer(r"\b[A-Za-z]*\d[A-Za-z0-9-]{1,24}\b", question or ""):
        term = match.group(0).strip("-")
        if len(term) >= 3:
            terms.append(term)
    return list(OrderedDict.fromkeys(terms))


def intelligence_for_question_and_sources(question, source_payload):
    result = {}
    for term in question_component_terms(question):
        for rel_path in vector_store.find_document_sources_by_term(term, limit=3):
            source_name = os.path.join(TRAINING_DIR, rel_path)
            if source_name in result:
                result[source_name]["questionMatch"] = True
                continue
            try:
                intelligence = get_or_build_datasheet_intelligence(source_name)
                intelligence["questionMatch"] = True
                result[source_name] = intelligence
            except Exception as exc:
                trace_logger.warning(f"Datasheet intelligence lookup failed for term {term}: {exc}")
    result.update({key: value for key, value in intelligence_for_sources(source_payload).items() if key not in result})
    return result


def get_response_cache():
    return db_response_cache


def current_index_fingerprint():
    return vector_store.catalog_fingerprint()


def build_response_cache_key(
    *,
    model_name,
    strategy,
    norm_q,
    retrieval_q,
    top_k,
    dist_thresh,
    max_tokens,
    show_full_text,
):
    return ResponseCacheKey(
        index_fingerprint=current_index_fingerprint(),
        model=model_name or "",
        strategy=strategy,
        question=norm_q,
        retrieval_query=retrieval_q,
        top_k=int(top_k),
        distance_threshold=round(float(dist_thresh), 6),
        max_tokens=int(max_tokens),
        show_full_text=bool(show_full_text),
    )


def build_runtime_status():
    vector_counts = vector_store.counts()
    image_counts = image_store.counts()
    image_ids = state.get_image_id_list()
    cpu_count = detected_cpu_count()
    return {
        "chunks": vector_counts.get("chunks", 0),
        "sources": vector_counts.get("documents", 0),
        "embeddings": vector_counts.get("embeddings", 0),
        "vectorChunks": vector_counts.get("chunks", 0),
        "vectorEmbeddings": vector_counts.get("embeddings", 0),
        "imageIds": len(image_ids),
        "imageEmbeddings": image_counts.get("embeddings", 0),
        "pendingReview": vector_store.pending_review_count(),
        "cacheStats": get_response_cache().stats(),
        "ingestWorkerBudget": {
            "cpuCores": cpu_count,
            "reservedCores": reserved_core_count(cpu_count),
            "usableCores": usable_core_count(cpu_count),
            "activeDocumentWorkers": active_document_worker_count() if index_status.get("running") else 0,
        },
        "ingest": dict(index_status),
    }


def build_readiness_status():
    runtime = build_runtime_status()
    checks = {
        "modelConfigured": bool(LLM_MODEL_NAME),
        "embeddingModelConfigured": bool(EMBED_MODEL_NAME),
        "textChunksLoaded": runtime["chunks"] > 0,
        "textIndexLoaded": runtime["vectorEmbeddings"] > 0,
        "embeddingsLoaded": runtime["embeddings"] > 0,
        "databaseConfigured": database.configured,
        "databaseReachable": database.health_check(),
    }
    ready = all(checks.values())
    return ready, {
        "status": "ready" if ready else "not_ready",
        "service": "CircuitShelf",
        "checks": checks,
        "runtime": runtime,
    }


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "CircuitShelf"}


@app.get("/readyz")
async def readyz():
    ready, payload = build_readiness_status()
    return JSONResponse(payload, status_code=200 if ready else 503)


def verify_user(username, password):
    return user_store.verify_user(username, password)


def bearer_token_from_request(req: Request) -> str:
    header = req.headers.get("authorization", "")
    prefix = "Bearer "
    if header.startswith(prefix):
        return header[len(prefix):].strip()
    return ""


def session_timeout_seconds() -> int:
    return max(60, int(config.get("SESSION_TIMEOUT_SECONDS", config.get("SESSION_TTL_SECONDS", 28800))))


def username_for_user(user) -> str | None:
    return getattr(user, "username", None) if user else None


def user_id_for_user(user) -> int | None:
    return getattr(user, "user_id", None) if user else None


def conversation_title_from_question(question: str) -> str:
    title = " ".join(str(question or "").split())
    if not title:
        return "New conversation"
    return title[:80]


USER_PREFERENCE_KEYS = {"ask.retrieval"}


def require_admin_user(req: Request):
    user = user_store.get_session(bearer_token_from_request(req), ttl_seconds=session_timeout_seconds())
    if not user:
        return None, JSONResponse({"error": "Authentication required."}, status_code=401)
    if not user.is_admin:
        return None, JSONResponse({"error": "Admin access required."}, status_code=403)
    return user, None


def require_authenticated_user(req: Request):
    if not database.configured or not user_store.has_active_users():
        return None, None
    user = user_store.get_session(bearer_token_from_request(req), ttl_seconds=session_timeout_seconds())
    if not user:
        return None, JSONResponse({"error": "Authentication required."}, status_code=401)
    return user, None


def safe_upload_filename(filename: str) -> str:
    name = os.path.basename(str(filename or "")).strip()
    if not name or name in {".", ".."}:
        raise ValueError("Upload must include a file name.")
    if name.startswith(".") or any(char in name for char in ("/", "\\")):
        raise ValueError("Upload file name is not allowed.")
    ext = os.path.splitext(name)[1].lower()
    if ext not in supported_training_extensions():
        allowed = ", ".join(sorted(supported_training_extensions()))
        raise ValueError(f"Unsupported file type. Allowed: {allowed}")
    return name


async def write_uploaded_documents(files: list[UploadFile], overwrite: bool) -> dict:
    if not files:
        raise ValueError("Upload must include at least one file.")

    os.makedirs(TRAINING_DIR, exist_ok=True)
    training_root = os.path.abspath(TRAINING_DIR)
    prepared = []
    seen_names = set()
    tmp_paths = []
    uploaded = []
    skipped = []

    try:
        for file in files:
            filename = safe_upload_filename(file.filename or "")
            if filename in seen_names:
                skipped.append({"filename": filename, "reason": "duplicate selection"})
                continue
            seen_names.add(filename)

            destination = os.path.abspath(os.path.join(TRAINING_DIR, filename))
            if not destination.startswith(training_root + os.sep):
                raise ValueError("Upload destination is outside the training directory.")
            if os.path.exists(destination) and not overwrite:
                skipped.append({"filename": filename, "reason": "already exists"})
                continue

            tmp_path = os.path.join(TRAINING_DIR, f".{filename}.{uuid.uuid4().hex}.upload")
            prepared.append((file, filename, destination, tmp_path))
            tmp_paths.append(tmp_path)

        for file, filename, destination, tmp_path in prepared:
            bytes_written = 0
            with open(tmp_path, "wb") as out_file:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    out_file.write(chunk)
            if bytes_written <= 0:
                raise ValueError(f"Uploaded file was empty: {filename}")
            uploaded.append({
                "filename": filename,
                "destination": destination,
                "tmpPath": tmp_path,
                "bytes": bytes_written,
            })

        for item in uploaded:
            os.replace(item["tmpPath"], item["destination"])
        return {
            "uploaded": [{"filename": item["filename"], "bytes": item["bytes"]} for item in uploaded],
            "skipped": skipped,
        }
    except Exception:
        for tmp_path in tmp_paths:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        raise
    finally:
        for file in files:
            await file.close()


def review_document_payload(row):
    return {
        "source": row["source_path"],
        "displayName": row["display_name"],
        "status": row["status"],
        "sizeBytes": int(row["size_bytes"] or 0),
        "fileExtension": row["file_extension"],
        "chunkCount": int(row["chunk_count"] or 0),
        "imageCount": int(row["image_count"] or 0),
        "rawChunkCount": int(row["raw_chunk_count"] or 0),
        "droppedChunkCount": int(row["dropped_chunk_count"] or 0),
        "extractedImageCount": int(row["extracted_image_count"] or 0),
        "storedImageCount": int(row["stored_image_count"] or 0),
        "indexedImageTextCount": int(row["indexed_image_text_count"] or 0),
        "ocrImageTextCount": int(row["ocr_image_text_count"] or 0),
        "avgQuality": float(row["avg_quality"] or 0.0),
        "lowQualityCount": int(row["low_quality_count"] or 0),
        "lastIngestedAt": row["last_ingested_at"].isoformat() if row["last_ingested_at"] else None,
        "lastError": row["last_error"],
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def review_chunk_payload(row):
    return {
        "index": int(row["chunk_index"]),
        "section": row["section_title"] or "Unknown",
        "category": row["category"] or "Uncategorized",
        "page": row["page_number"],
        "tokens": int(row["token_count"] or 0),
        "quality": float(row["quality_score"] or 0.0),
        "isOcr": bool(row["is_ocr"]),
        "hasMath": bool(row["has_math"]),
        "sourceImageId": row["source_image_key"],
        "qualityFlags": list(row["quality_flags"] or []),
        "preview": row["chunk_text"][:700],
    }


def review_image_payload(row):
    return {
        "imageKey": row["image_key"],
        "caption": row["caption"] or row["image_key"],
        "page": row["page_number"],
        "width": int(row["width_px"] or 0),
        "height": int(row["height_px"] or 0),
        "imageMimeType": row["image_mime_type"] or "image/png",
        "imageBase64": row["image_base64"],
    }


@app.post("/api/login")
async def login(req: Request):
    data = await req.json()
    username = data.get("username", "")
    password = data.get("password", "")
    user = verify_user(username, password)
    if user:
        session = user_store.create_session(user, ttl_seconds=session_timeout_seconds())
        return {"ok": True, "userId": session.user_id, "username": session.username, "isAdmin": session.is_admin, "token": session.token}
    return {"ok": False, "error": "Invalid credentials"}


@app.post("/api/logout")
async def logout(req: Request):
    user_store.delete_session(bearer_token_from_request(req))
    return {"ok": True}


@app.get("/api/user/preferences/{key}")
async def user_preference_get(key: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    if key not in USER_PREFERENCE_KEYS:
        return JSONResponse({"error": "Unknown preference key."}, status_code=404)
    return {"key": key, "value": user_preferences_store.get(user_id_for_user(user), key, {})}


@app.put("/api/user/preferences/{key}")
async def user_preference_update(key: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    if key not in USER_PREFERENCE_KEYS:
        return JSONResponse({"error": "Unknown preference key."}, status_code=404)
    data = await req.json()
    return {"key": key, "value": user_preferences_store.set(user_id_for_user(user), key, data.get("value") or {})}


@app.get("/api/app-config")
async def app_config():
    return {
        "siteName": config.get("SITE_NAME", "CircuitShelf"),
        "models": LLM_MODEL_OPTIONS,
        "defaultModel": LLM_MODEL_NAME,
        "authConfigured": database.configured and user_store.has_active_users(),
        "retrievalStrategies": ["Vector only", "Vector + CrossEncoder"],
        "statusPollIntervalSeconds": max(5, int(config.get("STATUS_POLL_INTERVAL_SECONDS", 15))),
        "activeStatusPollIntervalSeconds": max(1, int(config.get("STATUS_POLL_ACTIVE_INTERVAL_SECONDS", 3))),
        "sessionTimeoutSeconds": session_timeout_seconds(),
        "defaults": {
            "topK": 15,
            "distanceThreshold": 4.0,
            "maxTokens": 1800,
            "showFullText": False,
            "bypassCache": True,
            "strategy": "Vector + CrossEncoder",
        },
    }


@app.get("/api/conversations")
async def conversations_list(req: Request, limit: int = 50):
    user, error = require_authenticated_user(req)
    if error:
        return error
    return {"conversations": conversation_store.list(user_id_for_user(user), limit=max(1, min(int(limit), 100)))}


@app.post("/api/conversations")
async def conversation_create(req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    data = await req.json()
    title = data.get("title") or "New conversation"
    conversation = conversation_store.create(user_id_for_user(user), title)
    return {"conversation": {**conversation, "turns": []}}


@app.get("/api/conversations/{conversation_id}")
async def conversation_get(conversation_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    conversation = conversation_store.get(conversation_id, user_id_for_user(user))
    if not conversation:
        return JSONResponse({"error": "Conversation not found."}, status_code=404)
    return {"conversation": conversation}


@app.delete("/api/conversations/{conversation_id}")
async def conversation_delete(conversation_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    removed = conversation_store.archive(conversation_id, user_id_for_user(user))
    if not removed:
        return JSONResponse({"error": "Conversation not found."}, status_code=404)
    return {"ok": True}


@app.get("/api/inventory/parts")
async def inventory_parts(req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    return {"parts": lab_inventory_store.list_parts(user_id_for_user(user))}


@app.post("/api/inventory/parts")
async def inventory_part_upsert(req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    data = await req.json()
    try:
        part = lab_inventory_store.upsert_part(user_id_for_user(user), data)
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"part": part}


@app.post("/api/inventory/import/preview")
async def inventory_import_preview(req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    data = await req.json()
    text = str(data.get("text") or "")
    if not text.strip():
        return JSONResponse({"error": "Inventory text is required."}, status_code=400)
    existing = lab_inventory_store.list_parts(user_id_for_user(user))
    return parse_inventory_import(text, existing)


@app.post("/api/inventory/import/apply")
async def inventory_import_apply(req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    data = await req.json()
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        return JSONResponse({"error": "At least one inventory item is required."}, status_code=400)
    user_id = user_id_for_user(user)
    existing_parts = {part["id"]: part for part in lab_inventory_store.list_parts(user_id)}
    saved = []
    for item in items[:200]:
        try:
            existing = existing_parts.get(str(item.get("existingPartId") or ""))
            if existing:
                item = {
                    **item,
                    "displayName": existing["displayName"],
                    "partType": existing["partType"],
                    "quantity": max(int(existing.get("quantity") or 0), int(item.get("quantity") or 0)),
                    "location": existing.get("location") or item.get("location") or "",
                    "notes": "\n".join(
                        note
                        for note in [
                            existing.get("notes") or "",
                            item.get("notes") or "",
                        ]
                        if note.strip()
                    ),
                    "aliases": sorted(set([*(existing.get("aliases") or []), *(item.get("aliases") or [])])),
                }
            saved.append(lab_inventory_store.upsert_part(user_id, item))
        except (TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
    return {"parts": saved, "count": len(saved)}


@app.delete("/api/inventory/parts/{part_id}")
async def inventory_part_delete(part_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    removed = lab_inventory_store.delete_part(user_id_for_user(user), part_id)
    if not removed:
        return JSONResponse({"error": "Inventory part not found."}, status_code=404)
    return {"ok": True}


@app.get("/api/inventory/project-candidates")
async def inventory_project_candidates(req: Request, limit: int = 24):
    user, error = require_authenticated_user(req)
    if error:
        return error
    return project_finder_store.find(user_id_for_user(user), limit=max(1, min(int(limit), 80)))


@app.get("/api/settings")
async def settings_list(req: Request):
    _, error = require_admin_user(req)
    if error:
        return error
    return {"settings": settings_store.list_editable()}


@app.put("/api/settings/{key}")
async def settings_update(key: str, req: Request):
    _, error = require_admin_user(req)
    if error:
        return error
    try:
        data = await req.json()
        updated = settings_store.update_setting(key, data.get("value"))
        change = runtime_settings.apply_update(key, updated["value"])
        if change.runtime_applied:
            trace_logger.info(f"⚙️ Applied runtime setting update for {key}.")
        elif change.restart_required:
            trace_logger.info(f"⚙️ Stored setting update for {key}; restart required to apply it.")
        return {"setting": updated}
    except KeyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    except (PermissionError, ValueError, TypeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/api/index/check")
async def index_check(req: Request):
    _, error = require_admin_user(req)
    if error:
        return error
    result = start_index_check("manual")
    return {"ok": True, **result}


@app.get("/api/review/documents")
async def review_documents(req: Request):
    _, error = require_admin_user(req)
    if error:
        return error
    return {"documents": [review_document_payload(row) for row in vector_store.list_review_documents()]}


@app.get("/api/review/document")
async def review_document(req: Request, source: str, limit: int = 50):
    _, error = require_admin_user(req)
    if error:
        return error
    rows = vector_store.review_document_chunks(source, limit=max(1, min(int(limit), 500)))
    if not rows:
        return {"document": source, "chunks": []}
    return {
        "document": source,
        "displayName": rows[0]["display_name"],
        "status": rows[0]["status"],
        "chunks": [review_chunk_payload(row) for row in rows],
    }


@app.get("/api/review/document/images")
async def review_document_images(req: Request, source: str):
    _, error = require_admin_user(req)
    if error:
        return error
    rows = image_store.list_review_images(source)
    return {"document": source, "images": [review_image_payload(row) for row in rows]}


@app.post("/api/review/document/approve")
async def review_document_approve(req: Request):
    user, error = require_admin_user(req)
    if error:
        return error
    data = await req.json()
    source = data.get("source", "")
    include_images = bool(data.get("includeImages", True))
    if not include_images:
        image_store.delete_document_images(source)
    row = vector_store.set_document_status(source, "indexed", user.username)
    if not row:
        return JSONResponse({"error": "Document not found."}, status_code=404)
    image_count = refresh_active_state_from_db()
    return {"ok": True, "document": dict(row), "imageCount": image_count}


@app.post("/api/review/document/reindex")
async def review_document_reindex(req: Request):
    _, error = require_admin_user(req)
    if error:
        return error
    data = await req.json()
    source = data.get("source", "")
    try:
        result = reindex_review_source(source)
    except FileNotFoundError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "chunks": result.chunks, "droppedChunks": result.dropped_chunks, "images": result.images}


@app.post("/api/review/document/remove")
async def review_document_remove(req: Request):
    _, error = require_admin_user(req)
    if error:
        return error
    data = await req.json()
    source = data.get("source", "")
    delete_file = bool(data.get("deleteFile", True))
    result, status_code = remove_document_from_store(source, delete_file=delete_file)
    if status_code != 200:
        return JSONResponse(result, status_code=status_code)
    return result


@app.post("/api/document/remove")
async def indexed_document_remove(req: Request):
    _, error = require_admin_user(req)
    if error:
        return error
    data = await req.json()
    source = data.get("source", "")
    delete_file = bool(data.get("deleteFile", True))
    result, status_code = remove_document_from_store(source, delete_file=delete_file)
    if status_code != 200:
        return JSONResponse(result, status_code=status_code)
    return result


@app.get("/api/assembly-plans")
async def assembly_plans(req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    return {"plans": assembly_plan_store.list(user_id_for_user(user))}


@app.get("/api/assembly-plans/{plan_id}")
async def assembly_plan(plan_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    plan = assembly_plan_store.get(plan_id, user_id_for_user(user))
    if not plan:
        return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
    return {"plan": plan}


@app.delete("/api/assembly-plans/{plan_id}")
async def assembly_plan_delete(plan_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    deleted = assembly_plan_store.delete(plan_id, user_id_for_user(user))
    if not deleted:
        return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
    return {"ok": True, "deleted": deleted}


@app.post("/api/assembly-plans/build")
async def assembly_plan_build(req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    data = await req.json()
    objective = str(data.get("objective") or "").strip()
    if not objective:
        return JSONResponse({"error": "Build objective is required."}, status_code=400)
    model_name = data.get("model") or LLM_MODEL_NAME

    _, answer, chat_history, sources, cache_stats, confidence, avg_time, build_card, validation = await run_in_threadpool(
        get_rag_response,
        question=objective,
        chat_history=[],
        show_full_text=False,
        top_k=int(data.get("topK", 15)),
        dist_thresh=float(data.get("distanceThreshold", 4.0)),
        max_tokens=int(data.get("maxTokens", 1800)),
        bypass_cache=True,
        strategy=data.get("strategy", "Vector + CrossEncoder"),
        model_name=model_name,
        user_id=user_id_for_user(user),
        username=username_for_user(user),
    )
    api_sources = normalize_sources_for_api(sources)
    if not build_card:
        recovery_prompt = build_recovery_prompt(objective, answer, api_sources)
        recovered = await run_in_threadpool(
            query_ollama_chat_with_retry,
            recovery_prompt,
            model_name,
            [],
            system_prompt=RECOVERY_SYSTEM_PROMPT,
        )
        build_card = parse_recovered_build_card(recovered, api_sources)
    if not build_card:
        return JSONResponse(
            {
                "error": "CircuitShelf could not build an assembly plan from the current indexed sources.",
                "answer": answer,
                "sources": api_sources,
                "confidence": confidence,
                "averageQueryTime": avg_time,
                "cacheStats": cache_stats,
                "chatHistory": chat_history,
                "validation": validation,
            },
            status_code=422,
        )

    plan = assembly_plan_store.create_from_card(
        question=objective,
        card=build_card,
        user_id=user_id_for_user(user),
        created_by=username_for_user(user),
    )
    return {
        "plan": plan,
        "answer": answer,
        "sources": api_sources,
        "confidence": confidence,
        "averageQueryTime": avg_time,
        "cacheStats": cache_stats,
        "chatHistory": chat_history,
        "validation": validation,
    }


@app.patch("/api/assembly-plans/{plan_id}/steps/{step_id}")
async def assembly_step_update(plan_id: str, step_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    data = await req.json()
    updated = assembly_plan_store.set_step_completed(plan_id, step_id, bool(data.get("completed")), user_id_for_user(user))
    if not updated:
        return JSONResponse({"error": "Assembly step not found."}, status_code=404)
    plan = assembly_plan_store.get(plan_id, user_id_for_user(user))
    return {"plan": plan}


@app.post("/api/assembly-plans/{plan_id}/assistant")
async def assembly_assistant(plan_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    data = await req.json()
    message = str(data.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "Message is required."}, status_code=400)
    plan = assembly_plan_store.get(plan_id, user_id_for_user(user))
    if not plan:
        return JSONResponse({"error": "Assembly plan not found."}, status_code=404)

    assembly_plan_store.add_note(plan_id, "user", message, user_id_for_user(user))
    prompt = build_assembly_assistant_prompt(plan, message)
    assistant_answer = await run_in_threadpool(query_ollama_chat_with_retry, prompt, data.get("model") or LLM_MODEL_NAME, [])
    assembly_plan_store.add_note(plan_id, "assistant", assistant_answer, user_id_for_user(user))
    return {"plan": assembly_plan_store.get(plan_id, user_id_for_user(user)), "answer": assistant_answer}


@app.get("/api/assembly-plans/{plan_id}/steps/{step_id}/evidence")
async def assembly_step_evidence(plan_id: str, step_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    user_id = user_id_for_user(user)
    if not assembly_plan_store.get(plan_id, user_id):
        return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
    return assembly_plan_store.evidence_for_step(plan_id, step_id, user_id)


@app.get("/api/assembly-plans/{plan_id}/export")
async def assembly_plan_export(plan_id: str, req: Request, format: str = Query("markdown")):
    user, error = require_authenticated_user(req)
    if error:
        return error
    plan = assembly_plan_store.get(plan_id, user_id_for_user(user))
    if not plan:
        return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
    export = bench_tools.build_assembly_export(plan, format)
    return export


@app.get("/api/assembly-plans/{plan_id}/learning")
async def assembly_learning_get(plan_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    user_id = user_id_for_user(user)
    plan = assembly_plan_store.get(plan_id, user_id)
    if not plan:
        return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
    session = assembly_plan_store.get_learning(plan_id, user_id) or assembly_plan_store.start_learning(plan_id, user_id)
    return {"learning": build_learning_payload(plan, session)}


@app.patch("/api/assembly-plans/{plan_id}/learning")
async def assembly_learning_update(plan_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    user_id = user_id_for_user(user)
    data = await req.json()
    plan = assembly_plan_store.get(plan_id, user_id)
    if not plan:
        return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
    session = assembly_plan_store.get_learning(plan_id, user_id) or assembly_plan_store.start_learning(plan_id, user_id)
    current = int((session or {}).get("currentOrdinal") or 1)
    action = str(data.get("action") or "").lower()
    if action == "next":
        current += 1
    elif action == "previous":
        current -= 1
    elif action == "disable":
        session = assembly_plan_store.update_learning(plan_id, user_id, current_ordinal=current, mode_enabled=False)
        return {"learning": build_learning_payload(plan, session)}
    elif data.get("currentOrdinal") is not None:
        current = int(data.get("currentOrdinal"))
    max_ordinal = max((int(step["ordinal"]) for step in plan.get("steps", [])), default=1)
    current = max(1, min(current, max_ordinal))
    session = assembly_plan_store.update_learning(plan_id, user_id, current_ordinal=current, mode_enabled=True)
    return {"learning": build_learning_payload(plan, session)}


@app.post("/api/assembly-plans/{plan_id}/photo-check")
async def assembly_photo_check(plan_id: str, req: Request, file: UploadFile = File(...), note: str = Form("")):
    user, error = require_authenticated_user(req)
    if error:
        return error
    user_id = user_id_for_user(user)
    plan = assembly_plan_store.get(plan_id, user_id)
    if not plan:
        return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
    mime_type = file.content_type or "application/octet-stream"
    if not mime_type.startswith("image/"):
        return JSONResponse({"error": "Upload must be an image."}, status_code=400)
    image_bytes = await file.read()
    await file.close()
    if not image_bytes:
        return JSONResponse({"error": "Uploaded image is empty."}, status_code=400)
    if len(image_bytes) > 8 * 1024 * 1024:
        return JSONResponse({"error": "Photo is too large. Use an image under 8 MB."}, status_code=400)
    diagnostics = bench_tools.analyze_bench_photo(image_bytes)
    checklist = bench_tools.build_photo_checklist(plan, note, diagnostics)
    check = assembly_plan_store.add_photo_check(
        plan_id,
        user_id,
        image_mime_type=mime_type,
        image_base64=base64.b64encode(image_bytes).decode("ascii"),
        note=note,
        checklist=checklist,
        diagnostics=diagnostics,
    )
    return {"check": check, "checks": assembly_plan_store.photo_checks(plan_id, user_id)}


@app.get("/api/assembly-plans/{plan_id}/photo-checks")
async def assembly_photo_checks(plan_id: str, req: Request):
    user, error = require_authenticated_user(req)
    if error:
        return error
    user_id = user_id_for_user(user)
    if not assembly_plan_store.get(plan_id, user_id):
        return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
    return {"checks": assembly_plan_store.photo_checks(plan_id, user_id)}


def build_learning_payload(plan: dict, session: dict | None) -> dict:
    steps = plan.get("steps") or []
    current_ordinal = int((session or {}).get("currentOrdinal") or 1)
    current_step = next((step for step in steps if int(step.get("ordinal") or 0) == current_ordinal), None)
    if not current_step and steps:
        current_step = steps[0]
        current_ordinal = int(current_step.get("ordinal") or 1)
    prompt = ""
    if current_step:
        prompt = learning_prompt_for_step(current_step)
    return {
        "planId": plan.get("id"),
        "currentOrdinal": current_ordinal,
        "modeEnabled": bool((session or {}).get("modeEnabled", True)),
        "stepCount": len(steps),
        "currentStep": current_step,
        "prompt": prompt,
    }


def learning_prompt_for_step(step: dict) -> str:
    step_type = step.get("type")
    title = step.get("title") or "this step"
    if step_type == "wiring":
        return (
            f"Before doing step {step.get('ordinal')}, identify the source pin/rail and destination for {title}. "
            "Say what should be connected, then make the connection and verify continuity before moving on."
        )
    if step_type == "warning":
        return (
            f"Pause on caution step {step.get('ordinal')}. Explain the risk in your own words before continuing."
        )
    return (
        f"Before checking step {step.get('ordinal')}, predict what a correct circuit should show, then perform the test."
    )


def build_assembly_assistant_prompt(plan: dict, message: str) -> str:
    steps = "\n".join(
        f"{step['ordinal']}. [{'done' if step['completed'] else 'open'}] {step['title']}: {step['instruction']} {step.get('note') or ''}"
        for step in plan.get("steps", [])
    )
    sources = "\n".join(
        f"- {source['displayName']} pages {', '.join(str(page) for page in source.get('pages') or [])}"
        for source in plan.get("sources", [])
    )
    notes = "\n".join(
        f"{note['role']}: {note['message']}"
        for note in (plan.get("notes") or [])[-8:]
    )
    return (
        "You are CircuitShelf's electronics bench assistant. Use only the assembly plan, checklist, and source notes below. "
        "Give practical next-step guidance, checks to perform, expected readings or behavior when supported, and safety cautions. "
        "If the plan lacks enough evidence, say what is missing.\n\n"
        f"Assembly plan: {plan.get('title')}\n"
        f"Objective: {plan.get('objective')}\n"
        f"Component: {plan.get('componentName')} ({plan.get('componentType')})\n"
        f"Summary: {plan.get('summary')}\n\n"
        f"Checklist:\n{steps}\n\n"
        f"Sources:\n{sources}\n\n"
        f"Recent bench conversation:\n{notes}\n\n"
        f"User says: {message}\n\n"
        "Respond as a concise lab assistant."
    )


def remove_document_from_store(source: str, *, delete_file: bool = True) -> tuple[dict, int]:
    if not source:
        return {"error": "Document source is required."}, 400

    rel_source = vector_store.rel_path_for_source(source)
    row = vector_store.delete_document(rel_source)
    if not row:
        return {"error": "Document not found."}, 404
    prune_training_files_from_state([rel_source])
    deleted_file = False
    if delete_file:
        target = os.path.abspath(os.path.join(TRAINING_DIR, rel_source))
        training_root = os.path.abspath(TRAINING_DIR)
        if target.startswith(training_root + os.sep) and os.path.exists(target):
            os.remove(target)
            deleted_file = True
    trace_logger.info(f"🧹 Removed document from store: {rel_source} | deleted source file: {deleted_file}")
    return {"ok": True, "document": dict(row), "deletedFile": deleted_file}, 200


@app.post("/api/query")
async def react_query(req: Request):
    try:
        user, error = require_authenticated_user(req)
        if error:
            return error
        data = await req.json()
        question = data.get("question", "")
        if not question.strip():
            return {"error": "No question provided."}
        username = username_for_user(user)
        user_id = user_id_for_user(user)
        conversation_id = data.get("conversationId")
        conversation = None
        if conversation_id:
            conversation = conversation_store.get(str(conversation_id), user_id)
            if not conversation:
                return JSONResponse({"error": "Conversation not found."}, status_code=404)
        else:
            conversation = conversation_store.create(user_id, conversation_title_from_question(question))
            conversation_id = conversation["id"]

        _, answer, chat_history, sources, cache_stats, confidence, avg_time, build_card, validation = await run_in_threadpool(
            get_rag_response,
            question=question,
            chat_history=data.get("chatHistory", []),
            show_full_text=bool(data.get("showFullText", False)),
            top_k=int(data.get("topK", 15)),
            dist_thresh=float(data.get("distanceThreshold", 4.0)),
            max_tokens=int(data.get("maxTokens", 1800)),
            bypass_cache=bool(data.get("bypassCache", True)),
            strategy=data.get("strategy", "Vector + CrossEncoder"),
            model_name=data.get("model", LLM_MODEL_NAME),
            user_id=user_id,
            username=username,
        )
        stored_answer = chat_history[-1][1] if chat_history else answer
        conversation_store.append_turn(
            conversation_id=str(conversation_id),
            question=question,
            answer=stored_answer,
            model_name=data.get("model", LLM_MODEL_NAME),
            retrieval_strategy=data.get("strategy", "Vector + CrossEncoder"),
            confidence_score=confidence,
        )
        conversation = conversation_store.get(str(conversation_id), user_id)

        return {
            "conversation": conversation,
            "question": question,
            "answer": answer,
            "chatHistory": chat_history,
            "sources": normalize_sources_for_api(sources),
            "cacheStats": cache_stats,
            "confidence": confidence,
            "averageQueryTime": avg_time,
            "buildCard": build_card,
            "validation": validation,
        }
    except Exception as e:
        trace_logger.error(f"❌ [API] React query failed: {e}")
        return {"error": str(e)}


@app.get("/api/documents")
async def documents():
    docs = []
    for row in vector_store.list_document_stats():
        docs.append({
            "source": row["source_path"],
            "displayName": row["display_name"],
            "chunkCount": int(row["actual_chunk_count"] or row["chunk_count"] or 0),
            "imageCount": int(row["actual_image_count"] or row["stored_image_count"] or 0),
            "rawChunkCount": int(row["raw_chunk_count"] or 0),
            "droppedChunkCount": int(row["dropped_chunk_count"] or 0),
            "extractedImageCount": int(row["extracted_image_count"] or 0),
            "storedImageCount": int(row["stored_image_count"] or 0),
            "indexedImageTextCount": int(row["indexed_image_text_count"] or 0),
            "ocrImageTextCount": int(row["ocr_image_text_count"] or 0),
        })
    return {"documents": docs}


@app.post("/api/documents/upload")
async def upload_document(
    req: Request,
    file: UploadFile = File(...),
    overwrite: bool = Query(False),
):
    _, error = require_admin_user(req)
    if error:
        return error

    try:
        upload_result = await write_uploaded_documents([file], overwrite)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        trace_logger.error(f"❌ Document upload failed: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)

    uploaded_files = upload_result["uploaded"]
    skipped_files = upload_result["skipped"]
    filename = uploaded_files[0]["filename"] if uploaded_files else ""
    index_job = start_index_check(f"upload:{filename}") if uploaded_files else {"started": False, "status": dict(index_status)}
    return {
        "ok": True,
        "filename": filename,
        "bytes": sum(item["bytes"] for item in uploaded_files),
        "files": uploaded_files,
        "skippedFiles": skipped_files,
        "count": len(uploaded_files),
        "skippedCount": len(skipped_files),
        "indexing": index_job,
    }


@app.post("/api/documents/upload-batch")
async def upload_documents(
    req: Request,
    files: list[UploadFile] = File(...),
    overwrite: bool = Query(False),
):
    _, error = require_admin_user(req)
    if error:
        return error

    try:
        upload_result = await write_uploaded_documents(files, overwrite)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        trace_logger.error(f"❌ Batch document upload failed: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)

    uploaded_files = upload_result["uploaded"]
    skipped_files = upload_result["skipped"]
    reason = f"upload-batch:{len(uploaded_files)}"
    index_job = start_index_check(reason) if uploaded_files else {"started": False, "status": dict(index_status)}
    return {
        "ok": True,
        "files": uploaded_files,
        "skippedFiles": skipped_files,
        "count": len(uploaded_files),
        "skippedCount": len(skipped_files),
        "bytes": sum(item["bytes"] for item in uploaded_files),
        "indexing": index_job,
    }


def build_document_detail(doc_name):
    rows = []
    pages = OrderedDict()
    image_assets = []
    chunks = state.get_chunks()
    metadata = state.get_metadata()
    sources = state.get_sources()
    image_store_payload = state.get_image_store()
    image_captions = state.get_image_captions()
    image_text = state.get_image_page_text()
    image_mime_types = state.get_image_mime_types()

    for image_id, image_base64 in sorted(image_store_payload.items()):
        if not image_asset_belongs_to_document(image_id, doc_name):
            continue
        page = extract_page_number(image_id) or None
        image_payload = {
            "imageKey": image_id,
            "caption": image_captions.get(image_id, image_id),
            "page": page,
            "imageMimeType": image_mime_types.get(image_id, "image/png"),
            "imageBase64": image_base64,
            "ocrText": image_text.get(image_id, ""),
        }
        image_assets.append(image_payload)
        if page is not None:
            pages.setdefault(page, {"page": page, "chunks": [], "images": []})["images"].append(image_payload)

    for idx, source in enumerate(sources):
        meta = metadata[idx] if idx < len(metadata) else {}
        doc_source = document_source_from_metadata(source, meta)
        if doc_source != doc_name:
            continue
        text = chunks[idx] if idx < len(chunks) else ""
        row = {
            "index": idx,
            "section": meta.get("section", "Unknown"),
            "category": meta.get("category", "Uncategorized"),
            "page": meta.get("page"),
            "sourceImageId": source_image_id_from_metadata(source, meta),
            "tokens": TokenUtils.tokenize_len(text),
            "preview": text[:500],
        }
        rows.append(row)
        page = row["page"]
        if page is not None:
            page_entry = pages.setdefault(page, {"page": page, "chunks": [], "images": []})
            page_entry["chunks"].append(row)

    pinout_chunks = list(chunks)
    pinout_metadata = list(metadata)
    for image in image_assets:
        if image.get("ocrText"):
            pinout_chunks.append(image["ocrText"])
            pinout_metadata.append({"source": doc_name, "page": image.get("page")})
    pinout = extract_pinout_map(pinout_chunks, pinout_metadata, doc_name)
    intelligence = get_or_build_datasheet_intelligence(doc_name)
    return {
        "document": doc_name,
        "displayName": display_source_name(doc_name),
        "chunks": rows,
        "images": image_assets,
        "pages": sorted(pages.values(), key=lambda item: int(item["page"])),
        "ingestStats": next(
            (
                {
                    "rawChunkCount": int(row["raw_chunk_count"] or 0),
                    "chunkCount": int(row["actual_chunk_count"] or row["chunk_count"] or 0),
                    "droppedChunkCount": int(row["dropped_chunk_count"] or 0),
                    "extractedImageCount": int(row["extracted_image_count"] or 0),
                    "storedImageCount": int(row["stored_image_count"] or 0),
                    "indexedImageTextCount": int(row["indexed_image_text_count"] or 0),
                    "ocrImageTextCount": int(row["ocr_image_text_count"] or 0),
                }
                for row in vector_store.list_document_stats()
                if row["source_path"] == doc_name
            ),
            None,
        ),
        "pinout": intelligence.get("pinout") if intelligence.get("pinout", {}).get("pins") else pinout,
        "intelligence": intelligence,
    }


@app.get("/api/document")
async def document_detail_query(source: str):
    return build_document_detail(source)


@app.get("/api/documents/{doc_name:path}")
async def document_detail(doc_name: str):
    return build_document_detail(doc_name)


@app.get("/api/trace")
async def trace():
    return sanitize_for_json(state.get_last_trace())


@app.get("/api/status")
async def status():
    return build_runtime_status()


@app.get("/api/status/log-tail")
async def status_log_tail(req: Request, lines: int = Query(200, ge=20, le=1000)):
    _, error = require_admin_user(req)
    if error:
        return error

    flush_trace_log()
    tail = tail_text_file(current_trace_log_file(), max_lines=lines)
    return {
        "path": tail.path,
        "exists": tail.exists,
        "sizeBytes": tail.size_bytes,
        "lines": tail.lines,
        "truncated": tail.truncated,
        "error": tail.error,
        "lineCount": len(tail.lines),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def mount_react_app():
    dist_dir = os.path.abspath(REACT_DIST_DIR)
    index_html = os.path.join(dist_dir, "index.html")
    assets_dir = os.path.join(dist_dir, "assets")
    if not os.path.exists(index_html):
        trace_logger.warning(f"React dist not found at {dist_dir}; API will run without static UI.")
        return
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="react-assets")

    @app.get("/")
    async def react_index():
        return FileResponse(index_html)

    @app.get("/{full_path:path}")
    async def react_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("assets/"):
            return {"error": "Not found"}
        return FileResponse(index_html)

def flush_trace_log():
    for handler in trace_logger.handlers:
        if hasattr(handler, 'flush'):
            handler.flush()


def current_trace_log_file():
    for handler in trace_logger.handlers:
        base_filename = getattr(handler, "baseFilename", None)
        if base_filename:
            return base_filename
    return TRACE_LOG_FILE
            


def start_app_server(host, port):

    uv_config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(uv_config)
    server.run()


if __name__ == "__main__":

    app_host = config.get("APP_HOST", config.get("API_HOST", "127.0.0.1"))
    app_port = config.get("APP_PORT", config.get("API_PORT", 1964))
    server_pid_file = config.get("SERVER_PID_FILE", "data/circuitshelf.pid")

    try:
        with acquire_process_lock(server_pid_file, name="CircuitShelf"):
            cleanup_stale_tesseract_temp_files()
            get_or_build_index()

            mount_react_app()
            trace_logger.info(f"🌐 CircuitShelf available at http://{app_host}:{app_port}")
            start_app_server(app_host, app_port)
    except ProcessLockError as exc:
        trace_logger.error(str(exc))
        raise SystemExit(1) from exc



