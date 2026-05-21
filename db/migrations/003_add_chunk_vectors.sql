BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS embedding_model text,
    ADD COLUMN IF NOT EXISTS embedding vector(768);

CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx
    ON document_chunks
    USING hnsw (embedding vector_l2_ops)
    WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS documents_status_idx
    ON documents (status);

INSERT INTO schema_migrations (version, name)
VALUES (3, 'add_chunk_vectors')
ON CONFLICT (version) DO NOTHING;

COMMIT;
