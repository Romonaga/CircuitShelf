SELECT resource_class, status, count(*) AS count
  FROM local_gpu_work_items
 WHERE status IN ('queued', 'running')
 GROUP BY resource_class, status
 ORDER BY resource_class, status;
