INSERT INTO assembly_plans (
    title,
    objective,
    component_name,
    component_type,
    summary,
    confidence,
    user_id,
    created_by,
    updated_at
)
SELECT %s, %s, %s, %s, %s, %s, %s, username, now()
FROM users
WHERE id = %s
RETURNING id;
