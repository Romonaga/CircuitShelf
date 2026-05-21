# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 06:54:37 2025

@author: sueco, rew
"""


# ===  Imports, Logging, and Configuration ===

import os
import re
import pickle
import requests
import time
import base64
import bcrypt
import zipfile
import atexit
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
from fastapi import Request
from collections import deque, OrderedDict
from docx import Document
from sentence_transformers import SentenceTransformer, CrossEncoder
from io import BytesIO
from PIL import Image
from nltk.tokenize import sent_tokenize
from requests.exceptions import RequestException
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles



#internal
from state_manager import StateManager
from chunking_util import ChunkingUtils
from tokenize_util import TokenUtils
from system_init import SystemInit
from persistence_module import PersistenceManager, PersistenceConfig
from training_logger import TrainingLogger
from reranker_module import Reranker
from ocr_utils import run_ocr
from index_builder import IndexBuilder
from ingest_manifest import IngestManifest
from conversation_manager import append_chat_turn, build_chat_messages, build_contextual_retrieval_query
from response_cache import (
    ResponseCacheEntry,
    ResponseCacheKey,
    build_index_fingerprint,
    should_cache_response,
)

#Inits the logger as well as the configuraqtion system
config, trace_logger = SystemInit.load_config_and_logger()
state = StateManager(use_lock=True, cache_capacity=200, trace_logger=trace_logger)
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
SAVE_EXTRACTED_IMAGES = config.get("SAVE_EXTRACTED_IMAGES", False)
INDEX_IMAGE_OCR_AS_TEXT = config.get("INDEX_IMAGE_OCR_AS_TEXT", False)
OCR_INDEX_TEXT_MIN_CHARS = config.get("OCR_INDEX_TEXT_MIN_CHARS", 80)
POST_TIMEOUT = config.get("POST_TIMEOUT", 60)
REACT_DIST_DIR = config.get("REACT_DIST_DIR", "frontend/dist")
QUERY_RETRIES = config.get("QUERY_RETRIES", 3)
QUERY_RETRY_DELAY = config.get("QUERY_RETRY_DELAY", 5)

# === File Extensions ===
DOC_EXT = config.get("DOC_EXT")
PDF_EXT = config.get("PDF_EXT")
MD_EXT = config.get("MD_EXT")



# === DataStore Files ===
INDEX_FILE = config.get("INDEX_FILE")
CHUNKS_FILE = config.get("CHUNKS_FILE")
SOURCES_FILE = config.get("SOURCES_FILE")
METADATA_FILE = config.get("METADATA_FILE")
EMBEDDINGS_FILE = config.get("EMBEDDINGS_FILE")
IMAGE_STORE_FILE = config.get("IMAGE_STORE_FILE")
IMAGE_CAPTIONS_FILE = config.get("IMAGE_CAPTIONS_FILE")
IMAGE_PAGE_TEXT_FILE = config.get("IMAGE_PAGE_TEXT_FILE")
IMAGE_EMBEDDINGS_FILE = config.get("IMAGE_EMBEDDINGS_FILE")
IMAGE_IDS_FILE = config.get("IMAGE_IDS_FILE")
CACHE_FILE = config.get("CACHE_FILE", "cache/cache.pkl")
IMAGE_BLOCK_HTML_FILE = config.get("IMAGE_BLOCK_HTML_FILE")

# === Directory Info ===
PROMPT_DIR = config.get("PROMPT_DIR", "prompts")
EXTRACTED_IMAGES_DIR = config.get("EXTRACTED_IMAGES_DIR", "extracted_images")
TRAINING_DIR = config.get("TRAINING_DIR", "training")
INGEST_MANIFEST_FILE = config.get("INGEST_MANIFEST_FILE", "data/ingest_manifest.json")


# === Stats and logging ===
TRAINING_OUTPUT_FILE = config.get("TRAINING_OUTPUT_FILE","trainingdata/training_output.jsonl")
BUILD_INDEX_LOG_FILE = config.get("BUILD_INDEX_LOG_FILE")


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



#This makes it simpler when we are saving and loading these files
#else you would have a very long signature.
persistence_config = PersistenceConfig(
    cache_file=CACHE_FILE,
    embeddings_file=EMBEDDINGS_FILE,
    index_file=INDEX_FILE,
    chunks_file=CHUNKS_FILE,
    sources_file=SOURCES_FILE,
    metadata_file=METADATA_FILE,
    image_store_file=IMAGE_STORE_FILE,
    image_captions_file=IMAGE_CAPTIONS_FILE,
    image_page_text_file=IMAGE_PAGE_TEXT_FILE,
    image_ids_file=IMAGE_IDS_FILE,
    image_embeddings_file=IMAGE_EMBEDDINGS_FILE
)
persistence = PersistenceManager(state, trace_logger, persistence_config)



#used to see if the systme has been saved, so we can reload from disk
files_to_check = [
        INDEX_FILE,
        CHUNKS_FILE,
        SOURCES_FILE,
        METADATA_FILE,
        EMBEDDINGS_FILE,
        IMAGE_STORE_FILE,
        IMAGE_CAPTIONS_FILE,
        IMAGE_PAGE_TEXT_FILE,
        IMAGE_EMBEDDINGS_FILE,
        IMAGE_IDS_FILE]



token_utils = TokenUtils(state=state, trace_logger=trace_logger)
chunker = ChunkingUtils(state=state, token_utils=token_utils, config=config, trace_logger=trace_logger)

training_logger = TrainingLogger(output_path=TRAINING_OUTPUT_FILE,trace_logger=trace_logger)


#validat we have rerank profiles
config.validate_rerank_profiles(RERANK_PROFILES)

#now we will check to see that all file directories are there and if not create.
persistence.ensure_directories()

if not os.path.exists(IMAGE_BLOCK_HTML_FILE):
    trace_logger.critical(f"Could not find {IMAGE_BLOCK_HTML_FILE}")


# === Initialize Globals ===

embedder = SentenceTransformer(EMBED_MODEL_NAME)

reranker_engine = Reranker(config, state, chunker, trace_logger)
query_timings = deque(maxlen=100)


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
        manifest_path=INGEST_MANIFEST_FILE,
        training_dir=TRAINING_DIR,
        supported_extensions=supported_training_extensions(),
        recursive=config.get("TRAINING_RECURSIVE", True),
        excluded_dirs=config.get("TRAINING_EXCLUDE_DIRS", []),
        hash_files=config.get("INGEST_HASH_FILES", False),
    )


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
    removed_chunks = 0
    for chunk, source, meta in zip(state.get_chunks(), state.get_sources(), state.get_metadata()):
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

    state.set_chunks(kept_chunks)
    state.set_sources(kept_sources)
    state.set_metadata(kept_metadata)
    state.set_embeddings([])
    state.set_index(None)
    state.set_image_store(image_store)
    state.set_image_captions(image_captions)
    state.set_image_page_text(image_page_text)
    state.set_image_id_list([])
    state.set_image_embeddings(None)

    trace_logger.info(
        f"🧹 Pruned {removed_chunks} chunks and removed OCR/image state for "
        f"{len(rel_paths)} changed/removed training files."
    )


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

@trace_timer("save_image_text")
def save_image_text(image_data, image_text, base_name, output_dir, img_extension="png", txt_extension="txt") -> str:
   
    img_file_name = ""
    txt_file_name = ""

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:

        img_file_name = f"{base_name}.{img_extension}"
        img_file_path = os.path.join(output_dir, img_file_name)
        with open(img_file_path, "wb") as img_file:
            img_file.write(image_data)
            trace_logger.debug(f"✅ Saved image: {img_file_path}")

    except Exception as e:
        trace_logger.warning(f"❌ Failed to save: {img_file_name}  image to Dir: {output_dir} Error: {e}")
        
    try:

        txt_file_name = f"{base_name}.{txt_extension}"
        txt_file_path = os.path.join(output_dir, txt_file_name)
        with open(txt_file_path, "w", encoding="utf-8") as txt_file:
            txt_file.write(image_text)
            trace_logger.debug(f"✅ Saved text: {txt_file_path}")

    except Exception as e:
        trace_logger.warning(f"❌ Failed to save: {txt_file_name}  image to Dir: {output_dir} Error: {e}")
    
    return img_file_name

@trace_timer("load_pdf_text")
def load_pdf_text(path):
    """
    Extract text and images from a PDF file, perform OCR on images, and save images to a folder.
    """
    trace_logger.info(f"📅 Loading PDF: {path}")
    pdf = fitz.open(path)
    page_texts = []
    extra_chunks, extra_sources, extra_meta = [], [], []

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

                ocr_result = ocr_image_bytes(image_bytes, img_name)
                if not ocr_result["accepted"]:
                    log_fn = trace_logger.debug if ocr_result["skipped"] else trace_logger.warning
                    score = ocr_result["score"]
                    reason = ocr_result["reason"]
                    log_fn(f"⚠️ Dropped {img_name} — OCR score: {score:.2f}, reason: {reason}")
                    continue

                ocr_text = ocr_result["text"]
                score = ocr_result["score"]
                confidence = ocr_result["confidence"]
                web_image_bytes = image_bytes_to_png_bytes(image_bytes, img_name)

                trace_logger.info(f"🧠 OCR accepted for {img_name}: {len(ocr_text)} chars | score: {score:.2f}{format_confidence(confidence)}")

                state.add_image_store(img_name, base64.b64encode(web_image_bytes).decode("utf-8"))
                state.add_image_caption(img_name, f"Image from {os.path.basename(path)}, page {page_num+1}")
                
                # Save the image using the save_image helper
                if SAVE_EXTRACTED_IMAGES:
                    _ = save_image_text(web_image_bytes, ocr_text, img_name, EXTRACTED_IMAGES_DIR)

                state.add_image_page_text(img_name, ocr_text)
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

            except Exception as ex:
                trace_logger.warning(f"❌ Failed to process image on page {page_num+1}: {ex}")
                continue

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

                            if SAVE_EXTRACTED_IMAGES:
                                _ = save_image_text(web_img_data, ocr_text, img_name, EXTRACTED_IMAGES_DIR)

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
    
def encode_image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

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
    page_texts, img_chunks, img_sources, img_meta = load_pdf_text(fpath)
    text = "\n\n".join(page_texts)
    density = token_utils.estimate_token_density(text)
    if density > 40:
        trace_logger.warning(f"⚠️ High token density in {fpath}: {density:.2f} tokens/line")

    use_adaptive = config.get("USE_ADAPTIVE_CHUNKING", False)
    if use_adaptive:
        chunks, meta = chunker.adaptive_chunk_pages(page_texts, fpath)
    else:
        chunks, meta = chunker.smart_chunk_pages(page_texts, fpath)

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

        # Save OCR text
        if SAVE_EXTRACTED_IMAGES:
            save_image_text(web_img_data, ocr_text, img_name, EXTRACTED_IMAGES_DIR)

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
def load_documents_parallel(folder, files_selected, clear_existing=True):
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
    if clear_existing:
        state.clear_all()

    if not file_list:
        trace_logger.warning(f"⚠️ No supported documents found in '{folder}'.")
        return


    def process_file(fname):
        fpath = fname if os.path.isabs(fname) else os.path.join(folder, fname)
        try:
            thread_id = threading.get_ident()
            trace_logger.info(f"🛠️ Thread-{thread_id} started for {fname}")
            start = time.time()

            process_file_by_type(fpath, state, trace_logger, chunker, token_utils)

            elapsed = time.time() - start
            trace_logger.info(f"✅ Thread-{thread_id} finished {fname} in {elapsed:.2f}s")

        except Exception as e:
            trace_logger.error(f"❌ Error processing {fname}: {e}")

    configured_workers = config.get("MAX_DOCUMENT_WORKERS", multiprocessing.cpu_count())
    max_workers = max(1, min(configured_workers, multiprocessing.cpu_count(), len(file_list)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_file, fname): fname for fname in file_list}
        for future in as_completed(futures):
            future.result()

    if config.get("ENABLE_TOKEN_NORMALIZATION", False):
        token_utils.normalize_token_distribution()
    trace_logger.info(
        f"🚀 Finished loading. {len(state.get_chunks())} chunks, "
        f"{len(state.get_image_page_text())} accepted image OCR texts."
    )



@trace_timer("get_or_build_index")
def get_or_build_index():
    if not os.path.exists(TRAINING_DIR):
        trace_logger.error(f"❌ Training folder '{TRAINING_DIR}' not found! Cannot proceed.")
        exit(1)

    trace_logger.info("🔄 Starting index load or build...")
    start_time = time.time()
    files_exist = all(os.path.exists(f) for f in files_to_check)
    manifest = build_ingest_manifest()
    current_manifest = manifest.scan()

    if files_exist:
        try:
            persistence.load_all()
            chunks = state.get_chunks()
            embeddings = state.get_embeddings()
            index = state.get_index()

            if not chunks or not embeddings or index is None:
                raise ValueError("Incomplete state loaded — triggering rebuild.")

            if index.ntotal != len(embeddings):
                trace_logger.warning(f"⚠️ FAISS index count ({index.ntotal}) != embedding count ({len(embeddings)})")
                raise ValueError("Corrupted index")

            previous_manifest = manifest.load()
            if previous_manifest:
                changes = manifest.diff(previous_manifest, current_manifest)
                if not changes.has_changes:
                    duration = time.time() - start_time
                    SystemInit.log_build_info(trace_logger,chunks,embeddings,state.get_image_id_list(),
                        duration)

                    trace_logger.info(f"✅ Index loaded in {duration:.2f} sec")
                    return

                trace_logger.info(
                    f"🔁 Training changes detected. Added: {len(changes.added)}, "
                    f"modified: {len(changes.modified)}, removed: {len(changes.removed)}, "
                    f"unchanged: {len(changes.unchanged)}"
                )
                prune_training_files_from_state(changes.changed_or_removed)
                if changes.changed_or_added:
                    load_documents_parallel(
                        folder=TRAINING_DIR,
                        files_selected=changes.changed_or_added,
                        clear_existing=False,
                    )

                builder = IndexBuilder(state, chunker, embedder, config, trace_logger)
                build_result = builder.build()
                persistence.save_all()
                manifest.save(current_manifest)

                duration = time.time() - start_time
                SystemInit.log_build_info(
                    trace_logger,
                    state.get_chunks(),
                    state.get_embeddings(),
                    state.get_image_id_list(),
                    duration
                )
                trace_logger.info(
                    f"📊 Incremental rebuild complete. Chunks: {build_result.chunks}, "
                    f"Embeddings: {len(state.get_embeddings())}, Images: {build_result.images}, "
                    f"Dropped chunks: {build_result.dropped_chunks}"
                )
                trace_logger.info(f"✅ Incremental rebuild completed in {duration:.2f} sec")
                return

            manifest.save(current_manifest)
            trace_logger.info("🧾 No ingest manifest existed. Saved current training manifest as baseline.")
            duration = time.time() - start_time
            SystemInit.log_build_info(trace_logger,chunks,embeddings,state.get_image_id_list(),
                duration)
            
            trace_logger.info(f"✅ Index loaded in {duration:.2f} sec")
            return

        except Exception as e:
            trace_logger.warning(f"🧹 Load failed, rebuilding from scratch: {e}")

    # === Data Load or build ===
    load_documents_parallel(folder=TRAINING_DIR, files_selected=None)

    

    builder = IndexBuilder(state, chunker, embedder, config, trace_logger)
    try:
        build_result = builder.build()
    except ValueError as e:
        trace_logger.error(f"❌ Index build failed: {e}")
        return

    persistence.save_all()
    manifest.save(current_manifest)


    duration = time.time() - start_time
    SystemInit.log_build_info(
        trace_logger,
        state.get_chunks(),
        state.get_embeddings(),
        state.get_image_id_list(),
        duration
    )

    trace_logger.info(
        f"📊 Chunk count: {build_result.chunks}, "
        f"Embeddings: {len(state.get_embeddings())}, "
        f"Images: {build_result.images}, "
        f"Dropped chunks: {build_result.dropped_chunks}"
    )
    trace_logger.info(f"✅ Rebuild completed in {duration:.2f} sec")


@trace_timer("search_top_images")
def search_top_images(question, top_n=4):

    image_ids = state.get_image_id_list()
    if not state.image_embeddings or not image_ids:
        return []

    action_keywords = ["click", "enter", "select", "choose", "screen", "dashboard", "button", "setting"]

    # Embed the user's question
    query_emb = embedder.encode([question], convert_to_numpy=True).astype("float32")

    # Search FAISS image index
    distances, indices = state.image_embeddings.search(query_emb, top_n * 2)
    results = []

    for idx, dist in zip(indices[0], distances[0]):
        
        if idx < len(image_ids):
            img_id = image_ids[idx]
            score_boost = 0.0
            ocr_text = state.image_page_text.get(img_id, "").lower()

            if any(kw in ocr_text for kw in action_keywords):
                score_boost += 0.05

            results.append((img_id, dist - score_boost))

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


def deduplicate_hits_by_index(hits):
    best_by_index = {}
    for idx, distance in hits:
        if idx not in best_by_index or distance < best_by_index[idx]:
            best_by_index[idx] = distance
    return sorted(best_by_index.items(), key=lambda item: item[1])


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

def fuse_scores_with_ranks(faiss_hits, rerank_scores, question):
    q_lower = question.lower()
    selected_profile = "default"

    # Match profile based on keywords
    for profile_name, profile_data in RERANK_PROFILES.items():
        keywords = [str(kw).lower() for kw in profile_data.get("keywords", [])]
        if any(kw in q_lower for kw in keywords):
            selected_profile = profile_name
            break

    if selected_profile == "default":
        trace_logger.debug(f"No RERANK_PROFILE matched for question: '{question}'. Using default.")
    else:
        trace_logger.debug(f"Matched RERANK_PROFILE: {selected_profile}")

    profile_weights = RERANK_PROFILES.get(selected_profile, RERANK_PROFILES["default"])
    w_faiss = profile_weights.get("weight_faiss", 0.4)
    w_rerank = profile_weights.get("weight_rerank", 0.6)

    # Normalize FAISS distances to [0, 1]
    faiss_scores = [1.0 - min(d / 15.0, 1.0) for _, d in faiss_hits]
    rerank_scores = rerank_scores[:len(faiss_scores)]  # ensure alignment

    fused_results = []
    for (i, dist), faiss_score, rerank_score in zip(faiss_hits, faiss_scores, rerank_scores):
        fused = w_faiss * faiss_score + w_rerank * rerank_score
        fused_results.append((i, dist, rerank_score, fused))

    fused_results.sort(key=lambda x: x[3], reverse=True)  # sort by fused score
    return fused_results, selected_profile



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
    strategy="FAISS + CrossEncoder",
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
            return norm_q, cached.answer, chat_history, cached.sources, response_cache.stats(), confidence, get_average_query_time()
    else:
        if bypass_cache:
            trace_logger.debug("Response cache bypassed by request option.")
        elif chat_history:
            trace_logger.debug("Response cache skipped for conversational request.")

    trace_logger.info(f"🔍 Response cache MISS: {cache_key.digest()} | Executing query")

    if not cache_enabled:
        response_cache.misses += 1

    # === FAISS Retrieval ===
    all_hits = []
    faiss_start = time.time()
    for syn in synonyms:
        emb = embedder.encode([syn], convert_to_numpy=True).astype("float32")
        distances, indices = state.index.search(emb, top_k)
        for i, dist in zip(indices[0], distances[0]):
            adjusted = dist * (1 + 0.1 * (1 - len(state.chunks[i]) / 500))
            if adjusted < dist_thresh:
                all_hits.append((i, adjusted))
    faiss_duration = time.time() - faiss_start

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
        return norm_q, response, chat_history, "", response_cache.stats(), "0.00", get_average_query_time()

    dedup_hits = deduplicate_hits_by_index(all_hits)
    rerank_duration = None

    if strategy == "FAISS only":
        selected = sorted(dedup_hits, key=lambda x: x[1])[:top_k]
        selected_chunks = reranker_engine.build_chunk_payload(selected)
        confidence = chunker.compute_faiss_confidence(selected, dist_thresh)
        profile = "N/A"
    else:
        rerank_start = time.time()
        reranked_chunks, confidence, profile = reranker_engine.rerank_chunks(dedup_hits, retrieval_q)
        rerank_duration = time.time() - rerank_start
        selected_chunks = reranked_chunks
        if not selected_chunks:
            trace_logger.warning("⚠️ Reranker returned no chunks; falling back to top FAISS hits.")
            selected = sorted(dedup_hits, key=lambda x: x[1])[:top_k]
            selected_chunks = reranker_engine.build_chunk_payload(selected)
            confidence = chunker.compute_faiss_confidence(selected, dist_thresh)
            profile = f"{profile} (FAISS fallback)"

    selected_chunks = trim_chunks_to_token_budget(selected_chunks, max_tokens)

    # === Build Final Prompt
    context = "\n\n".join([c["text"] for c in selected_chunks])
    prompt = build_prompt(context, norm_q, chunker.is_math_heavy_question(norm_q))

    # === LLM Call
    response = query_ollama_chat_with_retry(prompt, model_name, chat_history=chat_history)

    # === Format Output
    image_md_blocks = build_image_markdown_blocks(retrieval_q) if show_full_text else []
    final_answer = _assemble_final_markdown(response, image_md_blocks)

    chat_history = append_chat_turn(
        chat_history,
        norm_q,
        response,
        max_turns=MAX_CHAT_HISTORY_TURNS,
        max_chars=MAX_CHAT_HISTORY_CHARS,
    )

    source_payload = build_source_payload(selected_chunks)
    source_text = "\n".join([c["source"] for c in selected_chunks])
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
        "faiss_duration": f"{faiss_duration:.2f}s",
        "rerank_duration": "N/A" if rerank_duration is None else f"{rerank_duration:.2f}s",
        "total_duration": f"{time.time() - start_time:.2f}s",
        "top_chunks": selected_chunks,
    })

    try:
        training_logger.log(
            question=norm_q,
            context=context,
            llm_response=response,
            model=model_name,
            sources=source_text,
            confidence=confidence,
            rerank_strategy=strategy
        )
    except Exception as e:
        trace_logger.warning(f"⚠️ Failed to log training sample: {e}")

    return norm_q, final_answer, chat_history, source_payload, response_cache.stats(), confidence, get_average_query_time()

@trace_timer("extract_doc_and_page")
def extract_doc_and_page(img_id):
    match = re.search(r"(.+?)_page(\d+)_img\d+", img_id)
    if match:
        doc_name, page_str = match.groups()
        return doc_name, int(page_str)
    return img_id, -1

@trace_timer("build_image_markdown_blocks")
def build_image_markdown_blocks(question):
    matched_images = search_top_images(question, top_n=10)
    
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



app = FastAPI()


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


def get_response_cache():
    return state.get_cache()


def current_index_fingerprint():
    index = state.get_index()
    return build_index_fingerprint(
        manifest_path=INGEST_MANIFEST_FILE,
        chunks_count=len(state.get_chunks()),
        embeddings_count=len(state.get_embeddings()),
        faiss_total=index.ntotal if index else 0,
    )


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
    index = state.get_index()
    image_index = state.get_image_embeddings()
    chunks = state.get_chunks()
    sources = state.get_sources()
    metadata = state.get_metadata()
    embeddings = state.get_embeddings()
    image_ids = state.get_image_id_list()
    document_sources = {
        document_source_from_metadata(source, metadata[idx] if idx < len(metadata) else {})
        for idx, source in enumerate(sources)
    }
    return {
        "chunks": len(chunks),
        "sources": len(document_sources),
        "embeddings": len(embeddings),
        "faissTotal": index.ntotal if index else 0,
        "imageIds": len(image_ids),
        "imageFaissTotal": image_index.ntotal if image_index else 0,
        "cacheStats": get_response_cache().stats(),
    }


def build_readiness_status():
    runtime = build_runtime_status()
    checks = {
        "modelConfigured": bool(LLM_MODEL_NAME),
        "embeddingModelConfigured": bool(EMBED_MODEL_NAME),
        "textChunksLoaded": runtime["chunks"] > 0,
        "textIndexLoaded": runtime["faissTotal"] > 0,
        "embeddingsLoaded": runtime["embeddings"] > 0,
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
    users = config.get("USERS", {})
    if username in users:
        stored_hash = users[username].get("hashed_password", "")
        return bool(stored_hash and bcrypt.checkpw(password.encode(), stored_hash.encode()))
    return False


@app.post("/api/login")
async def login(req: Request):
    data = await req.json()
    username = data.get("username", "")
    password = data.get("password", "")
    if verify_user(username, password):
        return {"ok": True, "username": username}
    return {"ok": False, "error": "Invalid credentials"}

@app.get("/api/app-config")
async def app_config():
    return {
        "siteName": config.get("SITE_NAME", "CircuitShelf"),
        "models": LLM_MODEL_OPTIONS,
        "defaultModel": LLM_MODEL_NAME,
        "authConfigured": bool(config.get("USERS", {})),
        "retrievalStrategies": ["FAISS only", "FAISS + CrossEncoder"],
        "defaults": {
            "topK": 15,
            "distanceThreshold": 4.0,
            "maxTokens": 1800,
            "showFullText": False,
            "bypassCache": True,
            "strategy": "FAISS + CrossEncoder",
        },
    }


@app.post("/api/query")
async def react_query(req: Request):
    try:
        data = await req.json()
        question = data.get("question", "")
        if not question.strip():
            return {"error": "No question provided."}

        _, answer, chat_history, sources, cache_stats, confidence, avg_time = get_rag_response(
            question=question,
            chat_history=data.get("chatHistory", []),
            show_full_text=bool(data.get("showFullText", False)),
            top_k=int(data.get("topK", 15)),
            dist_thresh=float(data.get("distanceThreshold", 4.0)),
            max_tokens=int(data.get("maxTokens", 1800)),
            bypass_cache=bool(data.get("bypassCache", True)),
            strategy=data.get("strategy", "FAISS + CrossEncoder"),
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
            "imageCount": len(doc["imageIds"]),
        })
    docs.sort(key=lambda item: item["displayName"].lower())
    return {"documents": docs}


def build_document_detail(doc_name):
    rows = []
    chunks = state.get_chunks()
    metadata = state.get_metadata()
    sources = state.get_sources()
    for idx, source in enumerate(sources):
        meta = metadata[idx] if idx < len(metadata) else {}
        doc_source = document_source_from_metadata(source, meta)
        if doc_source != doc_name:
            continue
        text = chunks[idx] if idx < len(chunks) else ""
        rows.append({
            "index": idx,
            "section": meta.get("section", "Unknown"),
            "category": meta.get("category", "Uncategorized"),
            "page": meta.get("page"),
            "sourceImageId": source_image_id_from_metadata(source, meta),
            "tokens": TokenUtils.tokenize_len(text),
            "preview": text[:500],
        })
    return {"document": doc_name, "displayName": display_source_name(doc_name), "chunks": rows}


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


# Shutdown Registration
def save_on_exit():
    persistence.save_all()

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

    get_or_build_index()
 
    atexit.register(save_on_exit)
    atexit.register(SystemInit.flush_logger, trace_logger)

    mount_react_app()
    trace_logger.info(f"🌐 CircuitShelf available at http://{app_host}:{app_port}")
    start_app_server(app_host, app_port)



