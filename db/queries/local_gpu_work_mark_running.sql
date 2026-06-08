UPDATE local_gpu_work_items
   SET status_id = 2,
       slot_index = %s,
       process_id = %s,
       started_at = coalesce(started_at, now()),
       updated_at = now(),
       wait_seconds = extract(epoch FROM (now() - created_at)),
       details = details || %s::jsonb
 WHERE task_id = %s::uuid
RETURNING wait_seconds;
