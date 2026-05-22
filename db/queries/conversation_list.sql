WITH turn_counts AS (
    SELECT conversation_id,
           count(*) AS turn_count,
           max(created_at) AS last_turn_at
    FROM conversation_turns
    GROUP BY conversation_id
)
SELECT c.id,
       c.username,
       c.title,
       coalesce(t.turn_count, 0) AS turn_count,
       c.created_at,
       c.updated_at,
       t.last_turn_at
FROM conversations c
LEFT JOIN turn_counts t ON t.conversation_id = c.id
WHERE c.archived_at IS NULL
  AND (%s::citext IS NULL OR c.username = %s::citext)
ORDER BY c.updated_at DESC, c.created_at DESC
LIMIT %s;
