BEGIN;

UPDATE rerank_profiles
SET weight_vector = 0.4,
    weight_rerank = 0.6,
    updated_at = now()
WHERE name = 'default';

UPDATE rerank_profiles
SET weight_vector = 0.55,
    weight_rerank = 0.45,
    updated_at = now()
WHERE name = 'technical';

INSERT INTO app_settings (key, value_type, text_value, description, updated_at)
VALUES ('MODEL_DEVICE', 'text', 'auto', 'Torch device used for local embedding and reranking models. Use auto, cuda, or cpu.', now())
ON CONFLICT (key) DO NOTHING;

INSERT INTO app_settings (key, value_type, boolean_value, description, updated_at)
VALUES ('EMBED_BATCH_AUTO', 'boolean', true, 'Allow CircuitShelf to raise embedding batch size based on detected GPU VRAM.', now())
ON CONFLICT (key) DO NOTHING;

INSERT INTO app_settings (key, value_type, integer_value, description, updated_at)
VALUES ('RERANK_BATCH_SIZE', 'integer', 32, 'Number of query/chunk pairs scored per cross-encoder batch.', now())
ON CONFLICT (key) DO NOTHING;

INSERT INTO app_settings (key, value_type, boolean_value, description, updated_at)
VALUES ('RERANK_BATCH_AUTO', 'boolean', true, 'Allow CircuitShelf to raise reranker batch size based on detected GPU VRAM.', now())
ON CONFLICT (key) DO NOTHING;

INSERT INTO schema_migrations (version, name)
VALUES (31, 'model_runtime_and_rerank_defaults')
ON CONFLICT (version) DO NOTHING;

COMMIT;
