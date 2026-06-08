UPDATE local_gpu_work_items
   SET updated_at = now()
 WHERE task_id = %s::uuid
   AND status_id = 2;
