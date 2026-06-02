SELECT jobs.id,
       jobs.reason,
       status.code AS status,
       jobs.requested_by_user_id,
       users.username AS requested_by_username,
       jobs.worker_pid,
       jobs.created_at,
       jobs.started_at,
       jobs.finished_at,
       jobs.last_error,
       jobs.details
FROM ingest_jobs jobs
JOIN ingest_job_statuses status ON status.id = jobs.status_id
LEFT JOIN users ON users.id = jobs.requested_by_user_id
ORDER BY jobs.created_at DESC, jobs.id DESC
LIMIT %s;
