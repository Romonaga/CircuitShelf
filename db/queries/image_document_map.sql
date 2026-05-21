SELECT id, source_path, display_name
FROM documents
WHERE status IN ('indexed', 'needs_review')
ORDER BY source_path;
