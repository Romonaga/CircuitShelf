SELECT id, role, message, created_at
FROM assembly_plan_notes
WHERE plan_id = %s
ORDER BY created_at ASC, id ASC;
