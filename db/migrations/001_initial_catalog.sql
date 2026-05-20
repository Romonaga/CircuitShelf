BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingest_files (
    id bigserial PRIMARY KEY,
    path text NOT NULL UNIQUE,
    size_bytes bigint NOT NULL,
    mtime_ns bigint NOT NULL,
    sha256 text,
    status text NOT NULL DEFAULT 'pending',
    last_ingested_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id bigserial PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL DEFAULT 'running',
    added_count integer NOT NULL DEFAULT 0,
    modified_count integer NOT NULL DEFAULT 0,
    removed_count integer NOT NULL DEFAULT 0,
    chunk_count integer NOT NULL DEFAULT 0,
    embedding_count integer NOT NULL DEFAULT 0,
    image_count integer NOT NULL DEFAULT 0,
    notes text
);

CREATE TABLE IF NOT EXISTS ingest_file_stats (
    file_id bigint PRIMARY KEY REFERENCES ingest_files(id) ON DELETE CASCADE,
    chunk_count integer NOT NULL DEFAULT 0,
    accepted_ocr_count integer NOT NULL DEFAULT 0,
    dropped_ocr_count integer NOT NULL DEFAULT 0,
    avg_ocr_score numeric(6, 4),
    avg_ocr_confidence numeric(6, 2),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations (version, name)
VALUES (1, 'initial_catalog')
ON CONFLICT (version) DO NOTHING;

COMMIT;
