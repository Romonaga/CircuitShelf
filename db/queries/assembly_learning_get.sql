SELECT als.plan_id,
       als.user_id,
       als.current_ordinal,
       als.mode_enabled,
       als.created_at,
       als.updated_at
FROM assembly_learning_sessions als
JOIN assembly_plans ap ON ap.id = als.plan_id
WHERE als.plan_id = %s
  AND als.user_id = %s
  AND ap.user_id = %s;
