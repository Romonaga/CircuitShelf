SELECT status, count(*) AS count
  FROM local_gpu_work_items
 WHERE resource_class = %s
   AND status IN ('queued', 'running')
 GROUP BY status
 ORDER BY status;
