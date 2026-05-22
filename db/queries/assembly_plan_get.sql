SELECT
    id,
    title,
    objective,
    component_name,
    component_type,
    summary,
    confidence,
    status,
    created_by,
    created_at,
    updated_at
FROM assembly_plans
WHERE id = %s;
