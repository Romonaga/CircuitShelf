SELECT DISTINCT process_id
  FROM local_gpu_work_items
 WHERE status_id IN (1, 2)
   AND process_id IS NOT NULL;
