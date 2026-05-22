from __future__ import annotations


SETTING_GROUPS = {
    "general": {
        "label": "General",
        "description": "Basic application identity and runtime behavior.",
    },
    "server": {
        "label": "Server",
        "description": "Host, port, retry, and timeout values. Most changes require restart.",
    },
    "security": {
        "label": "Security",
        "description": "Login sessions and administrator access behavior.",
    },
    "models": {
        "label": "Models",
        "description": "Ollama generation model plus embedding and reranking models.",
    },
    "conversation": {
        "label": "Conversation",
        "description": "How much chat history is sent back to the model.",
    },
    "ingestion": {
        "label": "Ingestion",
        "description": "Document location, watcher behavior, and indexing worker limits.",
    },
    "chunking": {
        "label": "Chunking",
        "description": "How extracted text is split and scored before embedding.",
    },
    "retrieval": {
        "label": "Retrieval",
        "description": "Search, rerank, and cache behavior used while answering questions.",
    },
    "ocr": {
        "label": "OCR",
        "description": "Image text extraction and quality thresholds.",
    },
    "prompts": {
        "label": "Prompts",
        "description": "System and retrieval prompts sent to the model.",
    },
}


SETTING_UI = {
    "SITE_NAME": ("general", "Site name", "Name shown in the web interface.", False),
    "APP_HOST": ("server", "Application host", "Network interface the FastAPI application binds to.", True),
    "APP_PORT": ("server", "Application port", "Port used by the FastAPI application.", True),
    "API_HOST": ("server", "Legacy application host", "Older name for the application host. Prefer APP_HOST in fresh installs.", True),
    "API_PORT": ("server", "Legacy application port", "Older name for the application port. Prefer APP_PORT in fresh installs.", True),
    "POST_TIMEOUT": ("server", "Ollama request timeout", "Seconds to wait for a model response before the request fails.", False),
    "QUERY_RETRIES": ("server", "Query retries", "How many times to retry a failed model request.", True),
    "QUERY_RETRY_DELAY": ("server", "Retry delay", "Seconds to wait between failed model request retries.", True),
    "SESSION_TIMEOUT_SECONDS": ("security", "Session timeout", "Seconds of idle browser time allowed before a login session expires.", False),
    "LLM_MODEL_NAME": ("models", "Default chat model", "Ollama model used for answers unless a user chooses another model.", False),
    "OLLAMA_API_URL": ("models", "Ollama API URL", "Base Ollama API URL, usually http://localhost:11434/api.", False),
    "LLM_TEMPERATURE": ("models", "Temperature", "Higher values make answers more varied; lower values make them more consistent.", False),
    "LLM_NUM_PREDICT": ("models", "Response token budget", "Maximum tokens Ollama should generate for one answer.", False),
    "LLM_NUM_CTX": ("models", "Context window", "Maximum context tokens requested from the Ollama model.", True),
    "EMBED_MODEL_NAME": ("models", "Embedding model", "Sentence-transformer model used to embed document chunks and queries.", True),
    "CROSS_ENCODER_MODEL": ("models", "Cross-encoder model", "Model used to rerank vector search matches.", True),
    "EMBED_BATCH_SIZE": ("models", "Embedding batch size", "Number of chunks embedded per model batch during ingestion.", True),
    "MAX_CHAT_HISTORY_TURNS": ("conversation", "History turns", "Number of previous user/assistant turns kept in model context.", False),
    "MAX_CHAT_HISTORY_CHARS": ("conversation", "History character limit", "Maximum chat-history characters sent to the model.", False),
    "TRAINING_DIR": ("ingestion", "Document folder", "Folder watched for source documents.", False),
    "TRAINING_RECURSIVE": ("ingestion", "Scan subfolders", "When enabled, ingestion includes supported documents in subfolders.", False),
    "INGEST_WATCH_ENABLED": ("ingestion", "Background watcher", "Automatically checks for new, changed, and removed documents.", False),
    "INGEST_WATCH_INTERVAL_SECONDS": ("ingestion", "Watcher interval", "Seconds between automatic document-change checks.", False),
    "MAX_DOCUMENT_WORKERS": ("ingestion", "Document workers", "Maximum documents processed concurrently during ingestion.", True),
    "INGEST_HASH_FILES": ("ingestion", "Hash file contents", "Use content hashes for change detection instead of size and modified time.", True),
    "STATUS_POLL_INTERVAL_SECONDS": ("ingestion", "Idle status refresh", "Seconds between browser status refreshes while indexing is idle.", False),
    "STATUS_POLL_ACTIVE_INTERVAL_SECONDS": ("ingestion", "Active status refresh", "Seconds between browser status refreshes while indexing is running.", False),
    "PDF_RENDER_VECTOR_PAGES": ("ingestion", "Render visual PDF pages", "Store vector-heavy PDF pages as searchable images for pinouts, figures, graphs, and package drawings.", False),
    "PDF_RENDER_MAX_PAGES_PER_DOC": ("ingestion", "Rendered PDF page limit", "Maximum visual PDF pages stored per document.", False),
    "PDF_RENDER_MIN_DRAWINGS": ("ingestion", "PDF drawing threshold", "Minimum vector drawing count before a PDF page is considered visually important.", True),
    "PDF_RENDER_ZOOM": ("ingestion", "PDF render scale", "Scale factor used when rendering visual PDF pages.", True),
    "PDF_RENDER_RASTER_PAGES": ("ingestion", "Render raster PDF pages", "Store raster-heavy scanned PDF pages as searchable image assets.", False),
    "PDF_RENDER_MIN_RASTER_COVERAGE": ("ingestion", "Raster page coverage", "Minimum page area covered by embedded images before a PDF page is considered raster-heavy.", True),
    "CHUNKING_MODE": ("chunking", "Chunking mode", "Strategy used to split documents before embedding.", False),
    "CHUNK_SIZE": ("chunking", "Target chunk size", "Approximate target size for generated text chunks.", False),
    "CHUNK_OVERLAP": ("chunking", "Chunk overlap", "Amount of neighboring context repeated between chunks.", False),
    "MIN_TOKENS_PER_CHUNK": ("chunking", "Minimum chunk tokens", "Chunks below this token count are usually discarded.", False),
    "MAX_TOKENS_PER_CHUNK": ("chunking", "Maximum chunk tokens", "Chunks above this token count are split or trimmed.", False),
    "MIN_CHUNK_QUALITY": ("chunking", "Minimum chunk quality", "Minimum quality score required before a chunk is indexed.", False),
    "USE_ADAPTIVE_CHUNKING": ("chunking", "Adaptive chunking", "Allows chunk sizing to adjust based on extracted content.", True),
    "ENABLE_MATH_HEAVY_CHUNKING": ("chunking", "Math-heavy chunking", "Uses math-aware behavior for documents with many equations or formulas.", True),
    "ENABLE_TOKEN_NORMALIZATION": ("chunking", "Token normalization", "Normalizes extracted text before chunk scoring.", True),
    "MIN_ACCEPTED_SCORE": ("retrieval", "Minimum retrieval score", "Minimum score accepted from retrieval before a chunk is considered relevant.", True),
    "RERANK_FALLBACK_TOP_K": ("retrieval", "Fallback result count", "Number of vector matches used when reranking does not produce enough results.", False),
    "LRU_CACHE_SIZE": ("retrieval", "Response cache size", "Maximum number of cached query responses kept by the runtime cache.", True),
    "USE_MULTITHREAD_OCR": ("ocr", "Parallel OCR", "Run OCR work with multiple threads during ingestion.", False),
    "INDEX_IMAGE_OCR_AS_TEXT": ("ocr", "Index OCR text", "Treat useful image OCR output as searchable text.", False),
    "TESSERACT_CMD": ("ocr", "Tesseract command", "Path to the Tesseract executable.", True),
    "MAX_OCR_THREADS": ("ocr", "OCR thread limit", "Maximum OCR threads used when parallel OCR is enabled.", True),
    "OCR_INDEX_TEXT_MIN_CHARS": ("ocr", "OCR index minimum characters", "Minimum useful OCR text length before image text is indexed.", True),
    "OCR_MIN_CONFIDENCE": ("ocr", "OCR minimum confidence", "Minimum Tesseract confidence accepted for OCR text.", True),
    "OCR_USE_TESSERACT_CONFIDENCE": ("ocr", "Use Tesseract confidence", "Use Tesseract confidence scores when evaluating OCR quality.", True),
    "OCR_MIN_LENGTH": ("ocr", "OCR minimum length", "Minimum raw OCR text length considered meaningful.", True),
    "OCR_MIN_MEANINGFUL_CHARS": ("ocr", "OCR meaningful characters", "Minimum non-noise characters required for useful OCR text.", True),
    "OCR_MIN_MEANINGFUL_WORDS": ("ocr", "OCR meaningful words", "Minimum word count required for useful OCR text.", True),
    "OCR_MIN_UNIQUE_CHARS": ("ocr", "OCR unique characters", "Minimum unique-character count used to reject repetitive OCR noise.", True),
    "OCR_MIN_ALPHA_RATIO": ("ocr", "OCR alpha ratio", "Minimum letter ratio required before OCR text is accepted.", True),
    "OCR_MAX_DIGIT_RATIO": ("ocr", "OCR digit ratio", "Maximum digit ratio allowed before OCR text is treated as low quality.", True),
    "OCR_MAX_SYMBOL_RATIO": ("ocr", "OCR symbol ratio", "Maximum symbol ratio allowed before OCR text is treated as low quality.", True),
    "OCR_MAX_SPACE_RATIO": ("ocr", "OCR space ratio", "Maximum whitespace ratio allowed before OCR text is treated as low quality.", True),
    "OCR_MAX_AVG_WORD_LEN": ("ocr", "OCR average word length", "Maximum average word length allowed before OCR text is treated as noise.", True),
    "OCR_LOW_CONTENT_MAX_SCORE": ("ocr", "OCR low-content score", "Maximum quality score assigned to OCR with too little useful content.", True),
    "OCR_SHORT_TEXT_MAX_SCORE": ("ocr", "OCR short-text score", "Maximum quality score assigned to OCR that is too short.", True),
    "OCR_TXT_DROP_SCORE": ("ocr", "OCR drop score", "OCR text below this score is dropped during ingestion.", True),
    "RAG_CHAT_SYSTEM_PROMPT": ("prompts", "Chat system prompt", "System prompt used for retrieval-grounded chat answers.", False),
    "PROMPT_TEMPLATE_GENERAL": ("prompts", "General answer prompt", "Prompt template used for normal retrieval answers.", False),
    "PROMPT_TEMPLATE_MATH": ("prompts", "Math answer prompt", "Prompt template used when the query or sources are math-heavy.", False),
}


def setting_metadata(key: str) -> dict[str, object] | None:
    item = SETTING_UI.get(key)
    if not item:
        return None
    group, label, description, advanced = item
    group_metadata = SETTING_GROUPS.get(group, SETTING_GROUPS["general"])
    return {
        "label": label,
        "group": group,
        "groupLabel": group_metadata["label"],
        "groupDescription": group_metadata["description"],
        "description": description,
        "advanced": advanced,
    }
