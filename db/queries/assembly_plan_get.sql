SELECT
    id,
    title,
    objective,
    component_name,
    component_type,
    summary,
    confidence,
    status,
    user_id,
    created_by,
    created_at,
    updated_at
FROM assembly_plans
WHERE id = %s
  AND (%s::bigint IS NULL OR user_id = %s::bigint);
