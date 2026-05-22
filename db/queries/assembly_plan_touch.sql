UPDATE assembly_plans
SET updated_at = now()
WHERE id = %s;
