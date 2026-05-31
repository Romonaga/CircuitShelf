BEGIN;

CREATE TABLE IF NOT EXISTS performance_work_types (
    id smallserial PRIMARY KEY,
    code text NOT NULL UNIQUE,
    display_name text NOT NULL,
    description text NOT NULL DEFAULT ''
);

INSERT INTO performance_work_types (id, code, display_name, description)
VALUES
    (1, 'index_check', 'Index check', 'Scans source documents and records whether ingestion work is needed.'),
    (2, 'document_ingest', 'Document ingest', 'Extracts, chunks, embeds, and stores source documents.'),
    (3, 'query', 'Query', 'Retrieval and local model answer generation.'),
    (4, 'ai_assist', 'AI assist', 'External provider validation or generation work.')
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description;

SELECT setval('performance_work_types_id_seq', GREATEST((SELECT coalesce(max(id), 1) FROM performance_work_types), 1), true);

CREATE TABLE IF NOT EXISTS performance_resource_samples (
    id bigserial PRIMARY KEY,
    sampled_at timestamptz NOT NULL DEFAULT now(),
    cpu_percent numeric(8, 2),
    process_cpu_percent numeric(8, 2),
    process_memory_bytes bigint,
    process_threads integer,
    system_memory_used_percent numeric(8, 2),
    gpu_percent numeric(8, 2),
    gpu_memory_used_percent numeric(8, 2),
    gpu_memory_used_mib numeric(12, 2),
    gpu_memory_total_mib numeric(12, 2),
    gpu_temperature_c numeric(8, 2),
    gpu_power_w numeric(8, 2),
    active_document_workers integer NOT NULL DEFAULT 0,
    embedding_batch_active integer NOT NULL DEFAULT 0,
    reranker_batch_active integer NOT NULL DEFAULT 0,
    chunks bigint NOT NULL DEFAULT 0,
    sources bigint NOT NULL DEFAULT 0,
    image_ids bigint NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS performance_resource_samples_time_idx
    ON performance_resource_samples (sampled_at DESC);

CREATE TABLE IF NOT EXISTS performance_work_runs (
    id bigserial PRIMARY KEY,
    work_type_id smallint REFERENCES performance_work_types(id) ON DELETE SET NULL,
    entity_id bigint REFERENCES entities(id) ON DELETE SET NULL,
    user_id bigint REFERENCES users(id) ON DELETE SET NULL,
    label text NOT NULL DEFAULT '',
    trigger_reason text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'completed',
    source_path text NOT NULL DEFAULT '',
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    duration_ms integer NOT NULL DEFAULT 0,
    chunks integer NOT NULL DEFAULT 0,
    images integer NOT NULL DEFAULT 0,
    dropped_chunks integer NOT NULL DEFAULT 0,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message text
);

CREATE INDEX IF NOT EXISTS performance_work_runs_time_idx
    ON performance_work_runs (started_at DESC);

CREATE INDEX IF NOT EXISTS performance_work_runs_type_time_idx
    ON performance_work_runs (work_type_id, started_at DESC);

INSERT INTO schema_migrations (version, name)
VALUES (21, 'performance_history')
ON CONFLICT (version) DO NOTHING;

COMMIT;
