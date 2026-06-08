SELECT statuses.code AS status, count(*) AS count
  FROM local_gpu_work_items work
  JOIN local_gpu_work_statuses statuses ON statuses.id = work.status_id
 WHERE work.resource_class = %s
   AND work.status_id IN (1, 2)
 GROUP BY statuses.code
 ORDER BY statuses.code;
