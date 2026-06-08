UPDATE documents
SET is_global = %s,
    entity_id = %s,
    updated_at = now()
WHERE source_path = %s
RETURNING source_path,
          display_name,
          (SELECT code FROM document_statuses WHERE id = documents.status_id) AS status,
          status_id,
          entity_id,
          is_global;
