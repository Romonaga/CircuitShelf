SELECT id, username, title, created_at, updated_at
FROM conversations
WHERE id = %s
  AND archived_at IS NULL
  AND (%s::citext IS NULL OR username = %s::citext);
