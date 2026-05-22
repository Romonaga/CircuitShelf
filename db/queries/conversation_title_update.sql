UPDATE conversations
SET title = %s,
    updated_at = now()
WHERE id = %s
RETURNING id;
