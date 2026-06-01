SELECT source_path, entity_id, is_global, created_by_user_id
FROM documents
WHERE source_path = ANY(%s);
