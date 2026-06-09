UPDATE local_gpu_work_items
   SET status_id = 4,
       finished_at = now(),
       updated_at = now(),
       duration_seconds = extract(epoch FROM (now() - coalesce(started_at, created_at))),
       error_message = coalesce(error_message, 'Recovered local GPU work item owned by a dead process.')
 WHERE status_id IN (1, 2)
   AND process_id = ANY(%s::integer[]);
