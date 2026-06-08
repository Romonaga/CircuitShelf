SELECT statuses.code AS status, work.resource_class, count(*) AS count
  FROM local_gpu_work_items work
  JOIN local_gpu_work_statuses statuses ON statuses.id = work.status_id
 WHERE work.created_at >= now() - (%s::text)::interval
 GROUP BY statuses.code, work.resource_class
 ORDER BY work.resource_class, statuses.code;
