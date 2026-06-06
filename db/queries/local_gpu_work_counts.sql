SELECT status, resource_class, count(*) AS count
  FROM local_gpu_work_items
 WHERE created_at >= now() - (%s::text)::interval
 GROUP BY status, resource_class
 ORDER BY resource_class, status;
