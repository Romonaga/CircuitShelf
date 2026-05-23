UPDATE assembly_learning_sessions
SET current_ordinal = %s,
    mode_enabled = %s,
    updated_at = now()
WHERE plan_id = %s
  AND user_id = %s
RETURNING plan_id, user_id, current_ordinal, mode_enabled, created_at, updated_at;
