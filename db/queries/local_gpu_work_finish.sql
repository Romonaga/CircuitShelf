UPDATE local_gpu_work_items
   SET status_id = %s,
       finished_at = now(),
       updated_at = now(),
       duration_seconds = extract(epoch FROM (now() - coalesce(started_at, created_at))),
       error_message = %s
 WHERE task_id = %s::uuid;
