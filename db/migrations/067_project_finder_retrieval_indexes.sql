BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS document_chunks_project_finder_text_trgm_idx
    ON document_chunks USING gin (lower(chunk_text) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS document_chunks_project_finder_section_trgm_idx
    ON document_chunks USING gin (lower(coalesce(section_title, '')) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS document_intelligence_project_finder_text_trgm_idx
    ON document_intelligence USING gin (
        lower(coalesce(component_name, '') || ' ' || coalesce(component_type, '') || ' ' || coalesce(summary, '')) gin_trgm_ops
    );

INSERT INTO schema_migrations (version, name)
VALUES (67, 'project_finder_retrieval_indexes')
ON CONFLICT (version) DO NOTHING;

COMMIT;
