import os

from db.runtime_config_store import RuntimeConfigStore
from db.settings import AppSettingsStore


DEFAULT_APP_SETTINGS = [
    ("SITE_NAME", "CircuitShelf", "Name shown in the web interface."),
    ("POST_TIMEOUT", 600, "Seconds allowed for one Ollama request before timing out."),
    ("QUERY_RETRIES", 3, "Retry attempts for transient local model calls."),
    ("QUERY_RETRY_DELAY", 5, "Seconds to wait between transient local model retries."),
    ("LLM_MODEL_NAME", "electronics-helper:latest", "Default local Ollama chat model."),
    ("OLLAMA_API_URL", "http://localhost:11434/api", "Base Ollama API URL."),
    ("LLM_TEMPERATURE", 0.2, "Default local model response temperature."),
    ("LLM_NUM_PREDICT", 3072, "Default maximum generated tokens for local answers."),
    ("LLM_NUM_CTX", 8192, "Default local model context window."),
    ("EMBED_MODEL_NAME", "sentence-transformers/all-mpnet-base-v2", "Sentence-transformer model used to embed document chunks and queries."),
    ("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2", "Model used to rerank vector search matches."),
    ("MODEL_DEVICE", "auto", "Torch device used for local embedding and reranking models."),
    ("EMBED_BATCH_SIZE", 16, "Configured embedding batch size before GPU-aware auto sizing."),
    ("EMBED_BATCH_AUTO", True, "Allow CircuitShelf to raise embedding batch size based on detected GPU VRAM."),
    ("RERANK_BATCH_SIZE", 32, "Configured reranker batch size before GPU-aware auto sizing."),
    ("RERANK_BATCH_AUTO", True, "Allow CircuitShelf to raise reranker batch size based on detected GPU VRAM."),
    ("MAX_CHAT_HISTORY_TURNS", 10, "Number of previous user/assistant turns kept in model context."),
    ("MAX_CHAT_HISTORY_CHARS", 10000, "Maximum chat-history characters sent to the model."),
    ("TRAINING_DIR", "training", "Folder watched for source documents."),
    ("TRAINING_RECURSIVE", True, "When enabled, ingestion includes supported documents in subfolders."),
    ("INGEST_WATCH_ENABLED", True, "Automatically checks for new, changed, and removed documents."),
    ("STATUS_POLL_INTERVAL_SECONDS", 15, "Browser status refresh interval while indexing is idle."),
    ("STATUS_POLL_ACTIVE_INTERVAL_SECONDS", 3, "Browser status refresh interval while indexing is running."),
    ("SESSION_TIMEOUT_SECONDS", 28800, "Seconds of idle time before a browser login session expires."),
    ("INGEST_WATCH_INTERVAL_SECONDS", 300, "Seconds between automatic document-change checks."),
    ("LOG_RETENTION_DAYS", 7, "Days to keep trace log files. Set to 0 to disable automatic cleanup."),
    ("PDF_RENDER_VECTOR_PAGES", True, "Render vector-heavy PDF pages as searchable images."),
    ("PDF_RENDER_MIN_DRAWINGS", 100, "Minimum vector drawing count before a PDF page is considered visual."),
    ("PDF_RENDER_ZOOM", 1.5, "Scale used when rendering visual PDF pages."),
    ("PDF_RENDER_RASTER_PAGES", True, "Render raster-heavy scanned PDF pages as searchable images."),
    ("PDF_RENDER_MIN_RASTER_COVERAGE", 0.8, "Minimum page image coverage before a PDF page is considered raster-heavy."),
    ("PDF_RENDER_OCR_PAGES", True, "OCR rendered visual PDF pages when extracted page text is too sparse for retrieval."),
    ("OCR_ENGINE", "tesseract", "OCR engine used during ingestion: tesseract CPU or paddleocr GPU with Tesseract fallback."),
    ("OCR_ENGINE_FALLBACK", True, "Internal safety setting. PaddleOCR always falls back to Tesseract when unavailable or failed."),
    ("PADDLEOCR_DEVICE", "gpu", "Internal setting. PaddleOCR is GPU-only in CircuitShelf."),
    ("PADDLEOCR_LANG", "en", "PaddleOCR recognition language code."),
    ("PADDLEOCR_ENGINE", "", "Optional PaddleOCR inference backend override. Leave blank for the default backend."),
    ("PADDLEOCR_TIMEOUT_SECONDS", 120, "Seconds allowed for one PaddleOCR image request before falling back."),
    ("USE_MULTITHREAD_OCR", True, "Run OCR work with multiple threads during ingestion."),
    ("INDEX_IMAGE_OCR_AS_TEXT", True, "Treat useful image OCR output as searchable text."),
    ("OCR_INDEX_TEXT_MIN_CHARS", 20, "Minimum useful OCR text length before image text is indexed."),
    ("OCR_MIN_CONFIDENCE", 45, "Minimum Tesseract confidence accepted for OCR text."),
    ("OCR_USE_TESSERACT_CONFIDENCE", True, "Use Tesseract confidence scores when evaluating OCR quality."),
    ("OCR_MIN_LENGTH", 6, "Minimum raw OCR text length considered meaningful."),
    ("OCR_MIN_MEANINGFUL_CHARS", 8, "Minimum alphanumeric OCR characters considered meaningful."),
    ("OCR_MIN_MEANINGFUL_WORDS", 2, "Minimum OCR words considered meaningful."),
    ("OCR_MIN_UNIQUE_CHARS", 4, "Minimum unique OCR characters considered meaningful."),
    ("OCR_MIN_ALPHA_RATIO", 0.25, "Minimum alphabetic ratio accepted for OCR text."),
    ("OCR_MAX_DIGIT_RATIO", 0.75, "Maximum numeric ratio accepted for OCR text."),
    ("OCR_MAX_SYMBOL_RATIO", 0.40, "Maximum symbol ratio accepted for OCR text."),
    ("OCR_MAX_SPACE_RATIO", 0.45, "Maximum whitespace ratio accepted for OCR text."),
    ("OCR_MAX_AVG_WORD_LEN", 22, "Maximum average OCR word length before text is considered low quality."),
    ("OCR_LOW_CONTENT_MAX_SCORE", 0.30, "Maximum score for OCR text with very little useful content."),
    ("OCR_SHORT_TEXT_MAX_SCORE", 0.45, "Maximum score for short OCR text."),
    ("OCR_TXT_DROP_SCORE", 0.25, "Drop OCR text below this quality score."),
    (
        "INGEST_LOCAL_AI_REVIEW_ENABLED",
        True,
        "Use the local Ollama model as the first ingestion QA pass when deterministic extraction detects component/datasheet risk.",
    ),
    (
        "INGEST_OPENAI_ASSIST_ENABLED",
        True,
        "Escalate ingestion QA to OpenAI only after deterministic/local review says paid repair is useful. Corpus uses the system key; entity documents use entity then user key fallback.",
    ),
    (
        "DATASHEET_OPENAI_REPAIR_ENABLED",
        True,
        "Use deterministic gates to repair weak datasheet pinout/fact extraction with OpenAI when a scoped key is configured.",
    ),
    ("RESPONSE_FINALIZER_ENABLED", True, "Run a second model pass to validate and clean up generated answers."),
    (
        "RESPONSE_FINALIZER_MODE",
        "always",
        "When to run answer validation: off, always, auto, issues, build, build_or_issues, low_confidence, build_or_low_confidence, or issues_or_build_or_low_confidence.",
    ),
    ("RESPONSE_FINALIZER_MIN_CONFIDENCE", 0.80, "Retrieval confidence threshold used by low-confidence finalizer modes."),
    ("RESPONSE_FINALIZER_MAX_CONTEXT_CHARS", 7000, "Maximum source-summary characters sent to the response finalizer."),
    ("RERANK_MAX_CONTEXT_CHUNKS", 15, "Maximum reranked text chunks sent into one RAG answer prompt after cross-encoder scoring."),
    (
        "LOCAL_LLM_MAX_CONCURRENT",
        1,
        "Maximum concurrent local Ollama chat requests. Use 1 for one local GPU so requests queue instead of competing.",
    ),
    (
        "LOCAL_LLM_QUEUE_TIMEOUT_SECONDS",
        300,
        "Seconds a local Ollama request may wait for the local model queue before failing.",
    ),
    (
        "LOCAL_GPU_LLM_SLOTS",
        "auto",
        "Local LLM GPU slots. Auto means one local Ollama generation lane per detected GPU.",
    ),
    (
        "LOCAL_GPU_CUDA_SLOTS",
        "auto",
        "CUDA batch work lanes for embedding and reranking. Auto uses a conservative per-GPU batch lane count.",
    ),
    (
        "LOCAL_GPU_OCR_SLOTS",
        "auto",
        "PaddleOCR CUDA lanes. Auto sizes from detected GPU count and VRAM, with 20GB+ GPUs allowed higher OCR concurrency.",
    ),
    (
        "LOCAL_GPU_QUEUE_TIMEOUT_SECONDS",
        300,
        "Seconds local GPU work may wait for a GPU slot before failing.",
    ),
    (
        "OLLAMA_KEEP_ALIVE",
        "30s",
        "How long Ollama keeps the chat model loaded after a request. Use 0 to unload immediately; longer values improve follow-up speed.",
    ),
    (
        "RAG_CHAT_SYSTEM_PROMPT",
        "You are CircuitShelf's retrieval-grounded electronics assistant. Use retrieved context as the source of truth. If the context is missing details, say what is missing. A CircuitShelf build card is an app-rendered bench card with parts, power notes, pin-by-pin wiring, checks, warnings, and source notes. If the user asks for a build card, treat that as a request for practical build-ready guidance; do not say you do not know what a build card is. For wiring questions, give practical pin-by-pin steps, power and ground details, and safety cautions.",
        "System prompt used by the retrieval chat endpoint.",
    ),
    ("RESPONSE_CACHE_CAPACITY", 200, "Maximum number of cached query responses kept by the Postgres-backed response cache."),
]


def bootstrap_database_settings(*, database, config, trace_logger) -> tuple[AppSettingsStore, RuntimeConfigStore]:
    settings_store = AppSettingsStore(database, trace_logger)
    seeded_settings = settings_store.seed_from_config(config.config)
    prompt_seeded = _seed_prompt_settings(settings_store, config)

    for key, value, description in DEFAULT_APP_SETTINGS:
        settings_store.seed_setting(key, value, description)

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
    return settings_store, runtime_config_store


def _seed_prompt_settings(settings_store: AppSettingsStore, config) -> int:
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
    return prompt_seeded
