WITH failed_status AS (
    SELECT id
    FROM ingest_job_statuses
    WHERE code = 'failed'
),
abandoned AS (
    SELECT jobs.id
    FROM ingest_jobs jobs
    JOIN ingest_job_statuses status ON status.id = jobs.status_id
    WHERE status.code = 'running'
)
UPDATE ingest_jobs jobs
SET status_id = failed_status.id,
    finished_at = now(),
    last_error = %s,
    details = coalesce(jobs.details, '{}'::jsonb) || coalesce(%s::jsonb, '{}'::jsonb)
FROM failed_status, abandoned
WHERE jobs.id = abandoned.id
RETURNING jobs.id,
          jobs.reason,
          jobs.worker_pid,
          jobs.started_at,
          jobs.finished_at;
