BEGIN;

CREATE TABLE IF NOT EXISTS document_ingest_scope_overrides (
    source_path text PRIMARY KEY,
    entity_id bigint REFERENCES entities(id) ON DELETE CASCADE,
    is_global boolean NOT NULL DEFAULT true,
    created_by_user_id bigint REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (is_global = true AND entity_id IS NULL)
        OR (is_global = false AND entity_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS document_ingest_scope_overrides_entity_idx
    ON document_ingest_scope_overrides (entity_id)
    WHERE entity_id IS NOT NULL;

INSERT INTO schema_migrations (version, name)
VALUES (25, 'document_ingest_scope_overrides')
ON CONFLICT (version) DO NOTHING;

COMMIT;
