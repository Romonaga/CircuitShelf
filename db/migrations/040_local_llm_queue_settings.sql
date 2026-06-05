BEGIN;

INSERT INTO app_settings (key, value_type, integer_value, description, updated_at)
VALUES
    (
        'LOCAL_LLM_MAX_CONCURRENT',
        'integer',
        1,
        'Maximum concurrent local Ollama chat requests. Use 1 for one local GPU so requests queue instead of competing.',
        now()
    ),
    (
        'LOCAL_LLM_QUEUE_TIMEOUT_SECONDS',
        'integer',
        300,
        'Seconds a local Ollama request may wait for the local model queue before failing.',
        now()
    )
ON CONFLICT (key) DO NOTHING;

INSERT INTO app_settings (key, value_type, text_value, description, updated_at)
VALUES
    (
        'OLLAMA_KEEP_ALIVE',
        'text',
        '30s',
        'How long Ollama keeps the chat model loaded after a request. Use 0 to unload immediately; longer values improve follow-up speed.',
        now()
    )
ON CONFLICT (key) DO NOTHING;

INSERT INTO schema_migrations (version, name)
VALUES (40, 'local_llm_queue_settings')
ON CONFLICT (version) DO NOTHING;

COMMIT;
