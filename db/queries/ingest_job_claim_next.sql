WITH next_job AS (
    SELECT jobs.id
    FROM ingest_jobs jobs
    JOIN ingest_job_statuses status ON status.id = jobs.status_id
    WHERE status.code = 'queued'
    ORDER BY jobs.created_at, jobs.id
    LIMIT 1
    FOR UPDATE SKIP LOCKED
),
running_status AS (
    SELECT id
    FROM ingest_job_statuses
    WHERE code = 'running'
)
UPDATE ingest_jobs jobs
SET status_id = running_status.id,
    started_at = now(),
    worker_pid = %s,
    last_error = NULL
FROM next_job, running_status
WHERE jobs.id = next_job.id
RETURNING jobs.id,
          jobs.reason,
          jobs.requested_by_user_id,
          jobs.created_at,
          jobs.started_at;
