BEGIN;

ALTER TABLE performance_resource_samples
    ADD COLUMN IF NOT EXISTS active_document_worker_capacity integer NOT NULL DEFAULT 0;

UPDATE performance_resource_samples
   SET active_document_worker_capacity = active_document_workers
 WHERE active_document_worker_capacity = 0
   AND active_document_workers > 0;

INSERT INTO schema_migrations (version, name)
VALUES (37, 'performance_worker_capacity')
ON CONFLICT (version) DO NOTHING;

COMMIT;
