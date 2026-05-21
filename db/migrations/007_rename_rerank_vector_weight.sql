BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'rerank_profiles'
          AND column_name = 'weight_faiss'
    ) THEN
        ALTER TABLE rerank_profiles
            RENAME COLUMN weight_faiss TO weight_vector;
    END IF;
END $$;

INSERT INTO schema_migrations (version, name)
VALUES (7, 'rename_rerank_vector_weight')
ON CONFLICT (version) DO NOTHING;

COMMIT;
