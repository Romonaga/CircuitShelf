SELECT status.code,
       count(jobs.id)::integer AS count
FROM ingest_job_statuses status
LEFT JOIN ingest_jobs jobs ON jobs.status_id = status.id
GROUP BY status.code
ORDER BY status.code;
