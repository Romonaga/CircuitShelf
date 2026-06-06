SELECT task_id::text,
       task_type,
       priority,
       owner,
       process_id,
       slot_index,
       status,
       wait_seconds,
       duration_seconds,
       error_message,
       details,
       created_at,
       started_at,
       finished_at,
       updated_at
  FROM local_gpu_work_items
 WHERE created_at >= now() - (%s::text)::interval
 ORDER BY created_at DESC
 LIMIT %s;
