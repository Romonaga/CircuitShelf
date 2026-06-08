SELECT source_path
FROM documents
WHERE status_id = 3
  AND (
      source_path ILIKE %s
      OR display_name ILIKE %s
  )
ORDER BY display_name
LIMIT %s;
