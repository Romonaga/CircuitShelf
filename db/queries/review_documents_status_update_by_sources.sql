UPDATE documents
SET status_id = %s,
    reviewed_by = NULL,
    reviewed_at = NULL,
    last_error = NULL,
    updated_at = now()
WHERE source_path = ANY(%s)
RETURNING source_path;
