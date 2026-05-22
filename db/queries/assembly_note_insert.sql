INSERT INTO assembly_plan_notes (plan_id, role, message)
VALUES (%s, %s, %s)
RETURNING id, role, message, created_at;
