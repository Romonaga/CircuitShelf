DELETE FROM documents
WHERE source_path = %s
RETURNING source_path, display_name;
