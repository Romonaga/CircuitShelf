INSERT INTO local_gpu_work_items (
    task_id,
    resource_class,
    task_type,
    priority,
    owner,
    process_id,
    details
) VALUES (
    %s::uuid,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s::jsonb
)
RETURNING id;
