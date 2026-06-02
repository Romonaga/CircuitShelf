INSERT INTO ingest_jobs (reason, requested_by_user_id, status_id, details)
SELECT %s,
       %s,
       status.id,
       coalesce(%s::jsonb, '{}'::jsonb)
FROM ingest_job_statuses status
WHERE status.code = 'queued'
RETURNING id, reason, requested_by_user_id, created_at;
