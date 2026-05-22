INSERT INTO assembly_plan_notes (plan_id, role, message)
SELECT %s, %s, %s
FROM assembly_plans
WHERE id = %s
  AND (%s::bigint IS NULL OR user_id = %s::bigint)
RETURNING id, role, message, created_at;
