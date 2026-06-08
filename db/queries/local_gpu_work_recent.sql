SELECT task_id::text,
       resource_class,
       task_type,
       priority,
       owner,
       process_id,
       slot_index,
       statuses.code AS status,
       status_id,
       wait_seconds,
       duration_seconds,
       error_message,
       details,
       created_at,
       started_at,
       finished_at,
       updated_at
  FROM local_gpu_work_items work
  JOIN local_gpu_work_statuses statuses ON statuses.id = work.status_id
 WHERE work.created_at >= now() - (%s::text)::interval
 ORDER BY work.created_at DESC
 LIMIT %s;
