UPDATE documents
SET is_global = %s,
    entity_id = %s,
    updated_at = now()
WHERE source_path = %s
RETURNING source_path, display_name, status, entity_id, is_global;
