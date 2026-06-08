UPDATE documents
SET status_id = %s,
    reviewed_by = %s,
    reviewed_at = now(),
    updated_at = now()
WHERE source_path = %s
RETURNING source_path,
          display_name,
          (SELECT code FROM document_statuses WHERE id = documents.status_id) AS status,
          status_id;
