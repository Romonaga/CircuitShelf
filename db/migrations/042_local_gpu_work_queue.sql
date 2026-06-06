BEGIN;

CREATE TABLE IF NOT EXISTS local_gpu_work_items (
    id bigserial PRIMARY KEY,
    task_id uuid NOT NULL UNIQUE,
    task_type text NOT NULL,
    priority integer NOT NULL DEFAULT 50,
    owner text,
    process_id integer,
    slot_index integer,
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'timed_out', 'cancelled')),
    wait_seconds numeric(12, 3),
    duration_seconds numeric(12, 3),
    error_message text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_local_gpu_work_items_queue
    ON local_gpu_work_items (status, priority, id)
    WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS idx_local_gpu_work_items_recent
    ON local_gpu_work_items (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_local_gpu_work_items_running
    ON local_gpu_work_items (status, updated_at)
    WHERE status = 'running';

INSERT INTO schema_migrations (version, name)
VALUES (42, 'local_gpu_work_queue')
ON CONFLICT (version) DO NOTHING;

COMMIT;
