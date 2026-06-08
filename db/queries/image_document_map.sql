SELECT id, source_path, display_name
FROM documents
WHERE status_id IN (1, 2, 3)
ORDER BY source_path;
