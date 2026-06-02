INSERT INTO ingest_runtime_status (id, status, updated_at)
VALUES (1, %s::jsonb, now())
ON CONFLICT (id) DO UPDATE
SET status = EXCLUDED.status,
    updated_at = now()
RETURNING updated_at;
