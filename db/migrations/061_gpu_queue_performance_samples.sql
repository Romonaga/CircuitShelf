BEGIN;

ALTER TABLE performance_resource_samples
    ADD COLUMN IF NOT EXISTS gpu_queue_active integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS gpu_queue_queued integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS gpu_queue_cuda_queued integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS gpu_queue_ocr_queued integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS gpu_queue_llm_queued integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS gpu_queue_current_wait_seconds numeric(12, 3),
    ADD COLUMN IF NOT EXISTS gpu_queue_recent_avg_wait_seconds numeric(12, 3),
    ADD COLUMN IF NOT EXISTS gpu_queue_recent_max_wait_seconds numeric(12, 3);

INSERT INTO schema_migrations (version, name)
VALUES (61, 'gpu_queue_performance_samples')
ON CONFLICT (version) DO NOTHING;

COMMIT;
