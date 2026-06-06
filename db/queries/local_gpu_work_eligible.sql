SELECT coalesce((
    SELECT NOT EXISTS (
        SELECT 1
          FROM local_gpu_work_items other
         WHERE other.status = 'queued'
           AND (
                other.priority < current_item.priority
                OR (
                    other.priority = current_item.priority
                    AND other.id < current_item.id
                )
           )
    )
      FROM local_gpu_work_items current_item
     WHERE current_item.task_id = %s::uuid
       AND current_item.status = 'queued'
), false) AS eligible;
