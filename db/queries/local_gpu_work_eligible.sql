SELECT coalesce((
    SELECT (
        SELECT count(*)
          FROM local_gpu_work_items other
         WHERE other.status_id = 1
           AND other.resource_class = current_item.resource_class
           AND (
                other.priority < current_item.priority
                OR (
                    other.priority = current_item.priority
                    AND other.id < current_item.id
                )
           )
    ) < %s::integer
      FROM local_gpu_work_items current_item
     WHERE current_item.task_id = %s::uuid
       AND current_item.status_id = 1
), false) AS eligible;
