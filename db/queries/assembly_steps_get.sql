SELECT
    id,
    ordinal,
    step_type,
    title,
    instruction,
    note,
    source_path,
    page_number,
    completed_at
FROM assembly_plan_steps
WHERE plan_id = %s
ORDER BY ordinal ASC;
