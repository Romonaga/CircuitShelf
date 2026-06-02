BEGIN;

ALTER TABLE performance_resource_samples
    ADD COLUMN IF NOT EXISTS cpu_power_w numeric(8, 2);

INSERT INTO schema_migrations (version, name)
VALUES (33, 'cpu_power_performance')
ON CONFLICT (version) DO NOTHING;

COMMIT;
