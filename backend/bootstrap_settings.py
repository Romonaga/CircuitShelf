import os

from db.runtime_config_store import RuntimeConfigStore
from db.settings import AppSettingsStore


DEFAULT_APP_SETTINGS = [
    ("STATUS_POLL_INTERVAL_SECONDS", 15, "Browser status refresh interval while indexing is idle."),
    ("STATUS_POLL_ACTIVE_INTERVAL_SECONDS", 3, "Browser status refresh interval while indexing is running."),
    ("SESSION_TIMEOUT_SECONDS", 28800, "Seconds of idle time before a browser login session expires."),
    ("INGEST_WATCH_INTERVAL_SECONDS", 300, "Seconds between automatic document-change checks."),
    ("LOG_RETENTION_DAYS", 14, "Days to keep trace log files. Set to 0 to disable automatic cleanup."),
    ("PDF_RENDER_VECTOR_PAGES", True, "Render vector-heavy PDF pages as searchable images."),
    ("PDF_RENDER_MAX_PAGES_PER_DOC", 8, "Maximum rendered visual PDF pages stored per document."),
    ("PDF_RENDER_MIN_DRAWINGS", 100, "Minimum vector drawing count before a PDF page is considered visual."),
    ("PDF_RENDER_ZOOM", 1.5, "Scale used when rendering visual PDF pages."),
    ("PDF_RENDER_RASTER_PAGES", True, "Render raster-heavy scanned PDF pages as searchable images."),
    ("PDF_RENDER_MIN_RASTER_COVERAGE", 0.8, "Minimum page image coverage before a PDF page is considered raster-heavy."),
    (
        "INGEST_OPENAI_ASSIST_ENABLED",
        False,
        "Use OpenAI during ingestion to review extraction quality. Corpus uses the system key; entity documents use entity then user key fallback.",
    ),
    ("RESPONSE_FINALIZER_ENABLED", True, "Run a second model pass to validate and clean up generated answers."),
    (
        "RESPONSE_FINALIZER_MODE",
        "always",
        "When to run answer validation: off, always, issues, build, build_or_issues, low_confidence, or build_or_low_confidence.",
    ),
    ("RESPONSE_FINALIZER_MIN_CONFIDENCE", 0.80, "Retrieval confidence threshold used by low-confidence finalizer modes."),
    ("RESPONSE_FINALIZER_MAX_CONTEXT_CHARS", 7000, "Maximum source-summary characters sent to the response finalizer."),
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
