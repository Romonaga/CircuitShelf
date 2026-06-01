SELECT source_path, entity_id, is_global, created_by_user_id
FROM document_ingest_scope_overrides
WHERE source_path = ANY(%s);
