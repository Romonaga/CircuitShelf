UPDATE assembly_plan_steps
SET completed_at = CASE WHEN %s THEN now() ELSE NULL END
WHERE id = %s
  AND plan_id = %s
RETURNING id;
