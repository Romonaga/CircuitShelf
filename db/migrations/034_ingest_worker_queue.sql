BEGIN;

CREATE TABLE IF NOT EXISTS ingest_job_statuses (
    id smallserial PRIMARY KEY,
    code text NOT NULL UNIQUE,
    display_name text NOT NULL
);

INSERT INTO ingest_job_statuses (code, display_name)
VALUES
    ('queued', 'Queued'),
    ('running', 'Running'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
    ('skipped', 'Skipped')
ON CONFLICT (code) DO UPDATE
SET display_name = EXCLUDED.display_name;

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id bigserial PRIMARY KEY,
    reason text NOT NULL,
    status_id smallint NOT NULL REFERENCES ingest_job_statuses(id),
    requested_by_user_id bigint REFERENCES users(id) ON DELETE SET NULL,
    worker_pid integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    last_error text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ingest_jobs_status_created_idx
    ON ingest_jobs (status_id, created_at);

CREATE INDEX IF NOT EXISTS ingest_jobs_requested_by_idx
    ON ingest_jobs (requested_by_user_id)
    WHERE requested_by_user_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS ingest_runtime_status (
    id integer PRIMARY KEY CHECK (id = 1),
    status jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO ingest_runtime_status (id, status)
VALUES (1, '{}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO schema_migrations (version, name)
VALUES (34, 'ingest_worker_queue')
ON CONFLICT (version) DO NOTHING;

COMMIT;
