SELECT task_id::text,
       resource_class,
       task_type,
       priority,
       owner,
       process_id,
       slot_index,
       statuses.code AS status,
       status_id,
       CASE
           WHEN status_id = 1 THEN extract(epoch FROM (now() - created_at))
           ELSE wait_seconds
       END AS wait_seconds,
       CASE
           WHEN status_id = 2 AND started_at IS NOT NULL THEN extract(epoch FROM (now() - started_at))
           ELSE duration_seconds
       END AS duration_seconds,
       error_message,
       details,
       created_at,
       started_at,
       finished_at,
       updated_at
  FROM local_gpu_work_items work
  JOIN local_gpu_work_statuses statuses ON statuses.id = work.status_id
 WHERE work.created_at >= now() - (%s::text)::interval
 ORDER BY CASE status_id
              WHEN 2 THEN 0
              WHEN 1 THEN 1
              ELSE 2
          END,
          updated_at DESC,
          created_at DESC
 LIMIT %s;
