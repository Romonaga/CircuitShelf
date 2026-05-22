UPDATE conversations
SET archived_at = now(),
    updated_at = now()
WHERE id = %s
  AND archived_at IS NULL
  AND (%s::citext IS NULL OR username = %s::citext)
RETURNING id;
