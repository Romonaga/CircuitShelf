UPDATE conversations
SET archived_at = now(),
    updated_at = now()
WHERE id = %s
  AND archived_at IS NULL
  AND (%s::bigint IS NULL OR user_id = %s::bigint)
RETURNING id;
