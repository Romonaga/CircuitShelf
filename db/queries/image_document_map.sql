SELECT id, source_path, display_name
FROM documents
WHERE status = 'indexed'
ORDER BY source_path;
