INSERT INTO assembly_learning_sessions (plan_id, user_id, current_ordinal, mode_enabled, updated_at)
SELECT id, %s, 1, true, now()
FROM assembly_plans
WHERE id = %s
  AND user_id = %s
ON CONFLICT (plan_id, user_id) DO UPDATE SET
    mode_enabled = true,
    updated_at = now()
RETURNING plan_id, user_id, current_ordinal, mode_enabled, created_at, updated_at;
