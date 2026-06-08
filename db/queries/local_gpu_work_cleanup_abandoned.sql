UPDATE local_gpu_work_items
   SET status = 'failed',
       finished_at = now(),
       updated_at = now(),
       duration_seconds = extract(epoch FROM (now() - coalesce(started_at, created_at))),
       error_message = coalesce(error_message, 'Abandoned local GPU work item recovered after process restart.')
 WHERE (
        status = 'running'
        AND updated_at < now() - (%s::text)::interval
    )
    OR (
        status = 'queued'
        AND created_at < now() - (%s::text)::interval
    );
