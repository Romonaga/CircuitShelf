INSERT INTO assembly_plans (
    title,
    objective,
    component_name,
    component_type,
    summary,
    confidence,
    created_by,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, now())
RETURNING id;
