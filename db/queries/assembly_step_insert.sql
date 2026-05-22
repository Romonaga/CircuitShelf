INSERT INTO assembly_plan_steps (
    plan_id,
    ordinal,
    step_type,
    title,
    instruction,
    note,
    source_path,
    page_number
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
