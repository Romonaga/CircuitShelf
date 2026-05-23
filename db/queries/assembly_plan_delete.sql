DELETE FROM assembly_plans
WHERE id = %s
  AND (%s::bigint IS NULL OR user_id = %s::bigint)
RETURNING id, title;
