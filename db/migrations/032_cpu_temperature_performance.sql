BEGIN;

ALTER TABLE performance_resource_samples
    ADD COLUMN IF NOT EXISTS cpu_temperature_c numeric(8, 2);

INSERT INTO schema_migrations (version, name)
VALUES (32, 'cpu_temperature_performance')
ON CONFLICT (version) DO NOTHING;

COMMIT;
