UPDATE documents
SET status = %s,
    reviewed_by = %s,
    reviewed_at = now(),
    updated_at = now()
WHERE source_path = %s
RETURNING source_path, display_name, status;
