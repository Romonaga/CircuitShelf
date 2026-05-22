UPDATE conversations
SET updated_at = now()
WHERE id = %s;
