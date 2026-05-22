UPDATE assembly_plan_steps
SET completed_at = CASE WHEN %s THEN now() ELSE NULL END
WHERE id = %s
  AND plan_id = %s
  AND EXISTS (
      SELECT 1
      FROM assembly_plans ap
      WHERE ap.id = assembly_plan_steps.plan_id
        AND (%s::bigint IS NULL OR ap.user_id = %s::bigint)
  )
RETURNING id;
