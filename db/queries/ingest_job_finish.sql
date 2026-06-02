UPDATE ingest_jobs jobs
SET status_id = status.id,
    finished_at = now(),
    last_error = %s,
    details = coalesce(%s::jsonb, '{}'::jsonb)
FROM ingest_job_statuses status
WHERE jobs.id = %s
  AND status.code = %s
RETURNING jobs.id,
          status.code AS status,
          jobs.finished_at;
