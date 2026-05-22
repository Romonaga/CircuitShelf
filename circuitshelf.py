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
import multiprocessing
import threading
import uvicorn
import nltk
from lxml import etree
from datetime import datetime, timezone
from fastapi import FastAPI, File, Query, Request, UploadFile
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
from index_builder import IndexBuilder
from pinout_extractor import extract_pinout_map
from datasheet_intelligence import build_datasheet_intelligence
from circuit_build_cards import build_circuit_build_card
from ingest_manifest import IngestManifest
from conversation_manager import append_chat_turn, build_chat_messages, build_contextual_retrieval_query
from db.connection import Database, database_url_from_config
from db.datasheet_intelligence_store import DatasheetIntelligenceStore
from db.image_store import ImageStore
from db.query_log_store import QueryLogStore
from db.response_cache_store import PostgresResponseCache
from db.settings import AppSettingsStore
from db.users import UserStore
from db.vector_store import VectorStore
from response_cache import (
    ResponseCacheEntry,
    ResponseCacheKey,
    should_cache_response,
)

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
settings_store.seed_setting("PDF_RENDER_VECTOR_PAGES", True, "Render vector-heavy PDF pages as searchable images.")
settings_store.seed_setting("PDF_RENDER_MAX_PAGES_PER_DOC", 8, "Maximum rendered visual PDF pages stored per document.")
settings_store.seed_setting("PDF_RENDER_MIN_DRAWINGS", 100, "Minimum vector drawing count before a PDF page is considered visual.")
settings_store.seed_setting("PDF_RENDER_ZOOM", 1.5, "Scale used when rendering visual PDF pages.")
applied_settings = settings_store.apply_to_config(config)
if seeded_settings or applied_settings:
    trace_logger.info(
        f"⚙️ DB settings active. Seeded: {seeded_settings}, "
        f"prompts: {prompt_seeded}, loaded: {applied_settings}"
    )
user_store = UserStore(database, trace_logger)
query_log_store = QueryLogStore(database, trace_logger)
vector_store = VectorStore(database, config.get("TRAINING_DIR", "training"), config.get("EMBED_MODEL_NAME"), trace_logger)
image_store = ImageStore(database, config.get("TRAINING_DIR", "training"), trace_logger)
intelligence_store = DatasheetIntelligenceStore(database, trace_logger)
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
MAX_OCR_THREADS = config.get("MAX_OCR_THREADS", 1)
PDF_RENDER_VECTOR_PAGES = config.get("PDF_RENDER_VECTOR_PAGES", True)
PDF_RENDER_MAX_PAGES_PER_DOC = config.get("PDF_RENDER_MAX_PAGES_PER_DOC", 8)
PDF_RENDER_MIN_DRAWINGS = config.get("PDF_RENDER_MIN_DRAWINGS", 100)
PDF_RENDER_ZOOM = config.get("PDF_RENDER_ZOOM", 1.5)
POST_TIMEOUT = config.get("POST_TIMEOUT", 60)
REACT_DIST_DIR = config.get("REACT_DIST_DIR", "frontend/dist")
QUERY_RETRIES = config.get("QUERY_RETRIES", 3)
QUERY_RETRY_DELAY = config.get("QUERY_RETRY_DELAY", 5)

# === File Extensions ===
DOC_EXT = config.get("DOC_EXT")
PDF_EXT = config.get("PDF_EXT")
MD_EXT = config.get("MD_EXT")



# === Directory Info ===
PROMPT_DIR = config.get("PROMPT_DIR", "prompts")
TRAINING_DIR = config.get("TRAINING_DIR", "training")


# === Stats and logging ===
BUILD_INDEX_LOG_FILE = config.get("BUILD_INDEX_LOG_FILE")
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
        "When the user asks how to build or wire something, give practical pin-by-pin "
        "steps, power and ground details, component values when supported by context, "
        "and safety cautions."
    ),
)
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
query_timings = deque(maxlen=100)
INDEX_JOB_LOCK = threading.Lock()
INDEX_PROGRESS_LOCK = threading.Lock()
INGEST_WATCH_STOP = threading.Event()
INGEST_WATCH_RESCHEDULE = threading.Event()
INGEST_WATCH_THREAD = None
index_status = {
    "enabled": bool(config.get("INGEST_WATCH_ENABLED", True)),
    "running": False,
    "stage": "idle",
    "currentFiles": [],
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


def update_index_progress(*, stage=None, current_file=None, finished_file=None, total_files=None, details=None):
    with INDEX_PROGRESS_LOCK:
        active_files = list(index_status.get("currentFiles") or [])
        if total_files is not None:
            index_status["totalFiles"] = int(total_files)
        if stage is not None:
            index_status["stage"] = stage
        if details is not None:
            index_status["details"] = details
        if current_file and current_file not in active_files:
            active_files.append(current_file)
        if finished_file:
            active_files = [name for name in active_files if name != finished_file]
            index_status["processedFiles"] = int(index_status.get("processedFiles") or 0) + 1
        index_status["currentFiles"] = active_files[:10]
        return dict(index_status)


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
        image_id_list=image_id_list,
    )

    trace_logger.info(
        f"🧹 Pruned {removed_chunks} chunks and removed OCR/image state for "
        f"{len(rel_paths)} changed/removed training files."
    )


def load_db_image_state():
    image_data, captions, page_text = image_store.load_state_payload()
    state.set_image_store(image_data)
    state.set_image_captions(captions)
    state.set_image_page_text(page_text)
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
        image_id_list=[],
    )
    return load_db_image_state()


def persist_db_image_state(file_records, target_state=None, rel_paths=None):
    target_state = target_state or state
    image_text = target_state.get_image_page_text()
    image_ids = target_state.get_image_id_list()
    image_embeddings = {}
    if image_ids:
        encoded = embedder.encode(
            [image_text[key] for key in image_ids],
            batch_size=config.get("EMBED_BATCH_SIZE", 32),
            convert_to_numpy=True,
        ).astype("float32")
        image_embeddings = {key: encoded[idx] for idx, key in enumerate(image_ids)}

    payload = {
        "file_records": file_records,
        "image_store": target_state.get_image_store(),
        "image_captions": target_state.get_image_captions(),
        "image_page_text": target_state.get_image_page_text(),
        "image_embeddings": image_embeddings,
        "embedding_model": EMBED_MODEL_NAME,
        "metadata": target_state.get_metadata(),
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
    configured_threads = max(1, int(MAX_OCR_THREADS or 1))
    cpu_threads = max(1, multiprocessing.cpu_count())
    return max(1, min(configured_threads, cpu_threads, item_count))


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

    trace_logger.info(f"🧵 OCR processing {len(image_jobs)} PDF images with {worker_count} workers")
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


def add_pdf_rendered_pages(path, target_state):
    if not PDF_RENDER_VECTOR_PAGES:
        return 0

    try:
        rendered_pages = render_pdf_visual_pages(
            path,
            max_pages=int(PDF_RENDER_MAX_PAGES_PER_DOC or 0),
            min_drawings=int(PDF_RENDER_MIN_DRAWINGS or 100),
            zoom=float(PDF_RENDER_ZOOM or 1.5),
        )
    except Exception as exc:
        trace_logger.warning(f"⚠️ Could not render vector PDF pages for {path}: {exc}")
        return 0

    for rendered_page in rendered_pages:
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
def load_pdf_text(path, target_state=None):
    """
    Extract text and images from a PDF file, perform OCR on images, and save images to a folder.
    """
    target_state = target_state or state
    trace_logger.info(f"📅 Loading PDF: {path}")
    pdf = fitz.open(path)
    page_texts = []
    extra_chunks, extra_sources, extra_meta = [], [], []
    image_jobs = []

    for page_num in range(len(pdf)):
        page = pdf[page_num]
        page_text = page.get_text().strip()
        page_texts.append(page_text)

        for img_index, img in enumerate(page.get_images(full=True)):
            try:
                xref = img[0]
                base_image = pdf.extract_image(xref)
                image_bytes = base_image["image"]
                img_name = f"{os.path.basename(path)}_page{page_num+1}_img{img_index+1}"
                image_jobs.append((len(image_jobs), page_num, img_index, image_bytes, img_name))

            except Exception as ex:
                trace_logger.warning(f"❌ Failed to process image on page {page_num+1}: {ex}")
                continue

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

    add_pdf_rendered_pages(path, target_state)

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
def process_pdf_file(fpath, state, trace_logger, chunker, token_utils):
    page_texts, img_chunks, img_sources, img_meta = load_pdf_text(fpath, state)
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
def process_file_by_type(fpath, state, trace_logger, chunker, token_utils):
    
    if os.path.isdir(fpath):
        trace_logger.warning(f"⚠️ Skipping directory: {fpath}")
        return
    
    ext = os.path.splitext(fpath)[1].lower()
    trace_logger.debug(f"Processing file: {fpath} with extension: {ext}")

    if ext in FILE_PROCESSORS:
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
        try:
            if progress_callback:
                progress_callback(stage="processing_documents", current_file=fname)
            thread_id = threading.get_ident()
            trace_logger.info(f"🛠️ Thread-{thread_id} started for {fname}")
            start = time.time()

            process_file_by_type(fpath, target_state, trace_logger, target_chunker, target_token_utils)

            elapsed = time.time() - start
            trace_logger.info(f"✅ Thread-{thread_id} finished {fname} in {elapsed:.2f}s")

        except Exception as e:
            trace_logger.error(f"❌ Error processing {fname}: {e}")
        finally:
            if progress_callback:
                progress_callback(stage="processing_documents", finished_file=fname)

    configured_workers = config.get("MAX_DOCUMENT_WORKERS", multiprocessing.cpu_count())
    max_workers = max(1, min(configured_workers, multiprocessing.cpu_count(), len(file_list)))
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

    ingested_state = None
    build_result = None
    if changed_rel_paths:
        ingested_state, ingest_token_utils, ingest_chunker = build_ingest_context()
        load_documents_parallel(
            folder=TRAINING_DIR,
            files_selected=changed_rel_paths,
            clear_existing=True,
            target_state=ingested_state,
            target_chunker=ingest_chunker,
            target_token_utils=ingest_token_utils,
            progress_callback=update_index_progress,
        )
        update_index_progress(
            stage="embedding_chunks",
            details={
                "documents": len(changed_rel_paths),
                "rawChunks": len(ingested_state.get_chunks()),
            },
        )
        builder = IndexBuilder(ingested_state, ingest_chunker, embedder, config, trace_logger)
        try:
            build_result = builder.build()
        except ValueError as exc:
            trace_logger.warning(f"⚠️ Changed documents produced no valid chunks: {exc}")
            if delete_rel_paths:
                vector_store.delete_sources(delete_rel_paths)
            return None
        update_index_progress(
            stage="persisting_chunks",
            details={
                "documents": len(changed_rel_paths),
                "chunks": build_result.chunks,
                "droppedChunks": build_result.dropped_chunks,
                "imageCandidates": build_result.images,
            },
        )
        vector_store.replace_sources(
            delete_rel_paths=delete_rel_paths,
            file_records=current_manifest,
            chunks=ingested_state.get_chunks(),
            sources=ingested_state.get_sources(),
            metadata=ingested_state.get_metadata(),
            embeddings=np.asarray(ingested_state.get_embeddings(), dtype="float32"),
            status="pending",
        )
        update_index_progress(
            stage="persisting_images",
            details={
                "documents": len(changed_rel_paths),
                "chunks": build_result.chunks,
                "imageCandidates": build_result.images,
            },
        )
        image_result = persist_db_image_state(current_manifest, target_state=ingested_state, rel_paths=changed_rel_paths)
        update_index_progress(
            stage="readying_review",
            details={
                "documents": len(changed_rel_paths),
                "chunks": build_result.chunks,
                **image_result,
            },
        )
        ready_sources = vector_store.set_sources_status(list(changed_rel_paths), "needs_review")
        trace_logger.info(f"✅ {len(ready_sources)} documents are ready for review.")
    elif delete_rel_paths:
        vector_store.delete_sources(delete_rel_paths)

    return build_result


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
    update_index_progress(
        stage="embedding_chunks",
        details={
            "documents": 1,
            "rawChunks": len(ingested_state.get_chunks()),
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
            "imageCandidates": build_result.images,
        },
    )
    vector_store.replace_sources(
        delete_rel_paths=[source],
        file_records=current_manifest,
        chunks=ingested_state.get_chunks(),
        sources=ingested_state.get_sources(),
        metadata=ingested_state.get_metadata(),
        embeddings=np.asarray(ingested_state.get_embeddings(), dtype="float32"),
        status="pending",
    )
    update_index_progress(
        stage="persisting_images",
        details={
            "documents": 1,
            "chunks": build_result.chunks,
            "imageCandidates": build_result.images,
        },
    )
    image_result = persist_db_image_state(current_manifest, target_state=ingested_state, rel_paths=[source])
    update_index_progress(stage="readying_review", details={"documents": 1, **image_result})
    vector_store.set_sources_status([source], "needs_review")
    return build_result


def check_for_training_changes(reason="watch"):
    if not INDEX_JOB_LOCK.acquire(blocking=False):
        trace_logger.info(f"⏳ Index check skipped for {reason}; another index job is running.")
        return set_index_status(lastResult="already_running")

    set_index_status(
        running=True,
        stage="scanning",
        currentFiles=[],
        processedFiles=0,
        totalFiles=0,
        lastStartedAt=utc_now_iso(),
        lastReason=reason,
        lastError=None,
        lastResult="running",
        details={},
    )
    start_time = time.time()
    try:
        manifest = build_ingest_manifest()
        current_manifest = manifest.scan()
        previous_manifest = vector_store.load_document_records()
        changes = manifest.diff(previous_manifest, current_manifest)
        if not changes.has_changes:
            trace_logger.info(f"✅ Index check found no training changes for {reason}.")
            return set_index_status(
                running=False,
                stage="idle",
                currentFiles=[],
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
        )
        build_result = run_incremental_ingest(changes, current_manifest)
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
            processedFiles=len(changes.changed_or_added),
            totalFiles=len(changes.changed_or_added),
            lastFinishedAt=utc_now_iso(),
            lastResult=result,
            lastChanges=file_changes_payload(changes),
            details={},
        )
    except Exception as exc:
        trace_logger.error(f"❌ Incremental index check failed for {reason}: {exc}")
        return set_index_status(
            running=False,
            stage="failed",
            currentFiles=[],
            lastFinishedAt=utc_now_iso(),
            lastResult="failed",
            lastError=str(exc),
            details={},
        )
    finally:
        cleanup_stale_tesseract_temp_files()
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
    interval = ingest_watch_interval_seconds()
    schedule_next_ingest_check(interval)
    trace_logger.info(f"👁️ Training watcher enabled. Checking every {interval} seconds.")

    while not INGEST_WATCH_STOP.is_set():
        remaining = seconds_until_next_ingest_check(interval)
        if INGEST_WATCH_STOP.wait(remaining):
            break
        if INGEST_WATCH_RESCHEDULE.is_set():
            INGEST_WATCH_RESCHEDULE.clear()
            continue
        schedule_next_ingest_check(interval)
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
def query_ollama_chat_with_retry(prompt, model_name, chat_history=None, retries=QUERY_RETRIES,
                                 delay=QUERY_RETRY_DELAY):

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
            RAG_CHAT_SYSTEM_PROMPT,
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
    model_name=LLM_MODEL_OPTIONS[0]
):
    start_time = time.time()
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
            )
            build_card = build_circuit_build_card(norm_q, cached.sources, intelligence_for_question_and_sources(norm_q, cached.sources))
            return norm_q, cached.answer, chat_history, cached.sources, response_cache.stats(), confidence, get_average_query_time(), build_card
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
        return norm_q, response, chat_history, [], response_cache.stats(), "0.00", get_average_query_time(), None

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

    # === LLM Call
    response = query_ollama_chat_with_retry(prompt, model_name, chat_history=chat_history)

    # === Format Output
    image_md_blocks = build_image_markdown_blocks(retrieval_q, selected_chunks) if show_full_text else []
    final_answer = _assemble_final_markdown(response, image_md_blocks)

    chat_history = append_chat_turn(
        chat_history,
        norm_q,
        response,
        max_turns=MAX_CHAT_HISTORY_TURNS,
        max_chars=MAX_CHAT_HISTORY_CHARS,
    )

    source_payload = build_source_payload(selected_chunks)
    build_card = build_circuit_build_card(norm_q, source_payload, intelligence_for_question_and_sources(norm_q, source_payload))
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
    )

    return norm_q, final_answer, chat_history, source_payload, response_cache.stats(), confidence, get_average_query_time(), build_card

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

<p><img src="data:image/png;base64,{img_data}" alt="{img_id}" style="max-width: 100%; height: auto;" /></p>

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


def require_admin_user(req: Request):
    user = user_store.get_session(bearer_token_from_request(req), ttl_seconds=session_timeout_seconds())
    if not user:
        return None, JSONResponse({"error": "Authentication required."}, status_code=401)
    if not user.is_admin:
        return None, JSONResponse({"error": "Admin access required."}, status_code=403)
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
        return {"ok": True, "username": session.username, "isAdmin": session.is_admin, "token": session.token}
    return {"ok": False, "error": "Invalid credentials"}


@app.post("/api/logout")
async def logout(req: Request):
    user_store.delete_session(bearer_token_from_request(req))
    return {"ok": True}


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
        config.config[key] = updated["value"]
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
    rows = vector_store.review_document_chunks(source, limit=max(1, min(int(limit), 200)))
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
    row = vector_store.delete_document(source)
    if not row:
        return JSONResponse({"error": "Document not found."}, status_code=404)
    prune_training_files_from_state([source])
    if delete_file:
        target = os.path.abspath(os.path.join(TRAINING_DIR, source))
        training_root = os.path.abspath(TRAINING_DIR)
        if target.startswith(training_root + os.sep) and os.path.exists(target):
            os.remove(target)
    return {"ok": True, "document": dict(row)}


@app.post("/api/query")
async def react_query(req: Request):
    try:
        data = await req.json()
        question = data.get("question", "")
        if not question.strip():
            return {"error": "No question provided."}

        _, answer, chat_history, sources, cache_stats, confidence, avg_time, build_card = await run_in_threadpool(
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
        )

        return {
            "question": question,
            "answer": answer,
            "chatHistory": chat_history,
            "sources": normalize_sources_for_api(sources),
            "cacheStats": cache_stats,
            "confidence": confidence,
            "averageQueryTime": avg_time,
            "buildCard": build_card,
        }
    except Exception as e:
        trace_logger.error(f"❌ [API] React query failed: {e}")
        return {"error": str(e)}


@app.get("/api/documents")
async def documents():
    grouped = {}
    metadata = state.get_metadata()
    for idx, source in enumerate(state.get_sources()):
        meta = metadata[idx] if idx < len(metadata) else {}
        doc_source = document_source_from_metadata(source, meta)
        doc = grouped.setdefault(
            doc_source,
            {
                "source": doc_source,
                "displayName": display_source_name(doc_source),
                "chunkCount": 0,
                "imageIds": set(),
            },
        )
        doc["chunkCount"] += 1
        image_id = source_image_id_from_metadata(source, meta)
        if image_id:
            doc["imageIds"].add(image_id)

    docs = []
    for doc in grouped.values():
        docs.append({
            "source": doc["source"],
            "displayName": doc["displayName"],
            "chunkCount": doc["chunkCount"],
            "imageCount": max(len(doc["imageIds"]), image_asset_count_for_document(doc["source"])),
        })
    docs.sort(key=lambda item: item["displayName"].lower())
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

    for image_id, image_base64 in sorted(image_store_payload.items()):
        if not image_asset_belongs_to_document(image_id, doc_name):
            continue
        page = extract_page_number(image_id) or None
        image_payload = {
            "imageKey": image_id,
            "caption": image_captions.get(image_id, image_id),
            "page": page,
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
            


def start_app_server(host, port):

    uv_config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(uv_config)
    server.run()


if __name__ == "__main__":

    app_host = config.get("APP_HOST", config.get("API_HOST", "127.0.0.1"))
    app_port = config.get("APP_PORT", config.get("API_PORT", 1964))

    cleanup_stale_tesseract_temp_files()
    get_or_build_index()

    mount_react_app()
    trace_logger.info(f"🌐 CircuitShelf available at http://{app_host}:{app_port}")
    start_app_server(app_host, app_port)



