BEGIN;

DELETE FROM app_settings
 WHERE key = 'LOCAL_GPU_QUEUE_SLOTS';

INSERT INTO schema_migrations (version, name)
VALUES (44, 'drop_legacy_local_gpu_queue_setting')
ON CONFLICT (version) DO NOTHING;

COMMIT;
