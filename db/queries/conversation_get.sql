SELECT id, user_id, username, title, created_at, updated_at
FROM conversations
WHERE id = %s
  AND archived_at IS NULL
  AND (%s::bigint IS NULL OR user_id = %s::bigint);
