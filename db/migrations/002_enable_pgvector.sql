BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

INSERT INTO schema_migrations (version, name)
VALUES (2, 'enable_pgvector')
ON CONFLICT (version) DO NOTHING;

COMMIT;
