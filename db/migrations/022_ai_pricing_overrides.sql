BEGIN;

CREATE TABLE IF NOT EXISTS ai_billing_scope_types (
    id smallserial PRIMARY KEY,
    code text NOT NULL UNIQUE,
    display_name text NOT NULL,
    description text NOT NULL DEFAULT ''
);

INSERT INTO ai_billing_scope_types (id, code, display_name, description)
VALUES
    (1, 'system', 'System', 'System-owned provider key and global fallback billing.'),
    (2, 'entity', 'Entity', 'Entity-owned provider key and entity billing.'),
    (3, 'user', 'User', 'User-owned provider key and personal billing.')
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description;

SELECT setval('ai_billing_scope_types_id_seq', GREATEST((SELECT coalesce(max(id), 1) FROM ai_billing_scope_types), 1), true);

CREATE TABLE IF NOT EXISTS ai_model_pricing_overrides (
    id bigserial PRIMARY KEY,
    provider_type_id smallint NOT NULL REFERENCES ai_provider_types(id) ON DELETE CASCADE,
    model_name text NOT NULL,
    billing_scope_type_id smallint NOT NULL REFERENCES ai_billing_scope_types(id) ON DELETE CASCADE,
    entity_id bigint REFERENCES entities(id) ON DELETE CASCADE,
    user_id bigint REFERENCES users(id) ON DELETE CASCADE,
    input_per_million numeric(12, 6) NOT NULL CHECK (input_per_million >= 0),
    cached_input_per_million numeric(12, 6) NOT NULL CHECK (cached_input_per_million >= 0),
    output_per_million numeric(12, 6) NOT NULL CHECK (output_per_million >= 0),
    currency text NOT NULL DEFAULT 'USD',
    updated_by bigint REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ai_pricing_override_scope_consistency CHECK (
        (billing_scope_type_id = 1 AND entity_id IS NULL AND user_id IS NULL)
        OR (billing_scope_type_id = 2 AND entity_id IS NOT NULL AND user_id IS NULL)
        OR (billing_scope_type_id = 3 AND entity_id IS NULL AND user_id IS NOT NULL)
    ),
    UNIQUE NULLS NOT DISTINCT (provider_type_id, model_name, billing_scope_type_id, entity_id, user_id)
);

CREATE INDEX IF NOT EXISTS ai_model_pricing_overrides_scope_idx
    ON ai_model_pricing_overrides (billing_scope_type_id, entity_id, user_id);

INSERT INTO schema_migrations (version, name)
VALUES (22, 'ai_pricing_overrides')
ON CONFLICT (version) DO NOTHING;

COMMIT;
