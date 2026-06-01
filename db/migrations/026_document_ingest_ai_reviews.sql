BEGIN;

CREATE TABLE IF NOT EXISTS document_ingest_ai_reviews (
    id bigserial PRIMARY KEY,
    source_path text NOT NULL REFERENCES documents(source_path) ON DELETE CASCADE,
    provider_type_id smallint REFERENCES ai_provider_types(id) ON DELETE SET NULL,
    model_name text NOT NULL DEFAULT '',
    paid_by text NOT NULL DEFAULT '',
    review_text text NOT NULL DEFAULT '',
    review_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    estimated_cost numeric(14, 8) NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_ingest_ai_reviews_source_created_idx
    ON document_ingest_ai_reviews (source_path, created_at DESC);

INSERT INTO schema_migrations (version, name)
VALUES (26, 'document_ingest_ai_reviews')
ON CONFLICT (version) DO NOTHING;

COMMIT;
