SELECT status, count(*) AS count
  FROM local_gpu_work_items
 WHERE created_at >= now() - (%s::text)::interval
 GROUP BY status
 ORDER BY status;
