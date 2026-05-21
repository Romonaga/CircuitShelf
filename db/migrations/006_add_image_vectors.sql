BEGIN;

ALTER TABLE document_images
    ADD COLUMN IF NOT EXISTS embedding_model text,
    ADD COLUMN IF NOT EXISTS embedding vector(768);

CREATE INDEX IF NOT EXISTS document_images_embedding_hnsw_idx
    ON document_images
    USING hnsw (embedding vector_l2_ops)
    WHERE embedding IS NOT NULL;

INSERT INTO schema_migrations (version, name)
VALUES (6, 'add_image_vectors')
ON CONFLICT (version) DO NOTHING;

COMMIT;
