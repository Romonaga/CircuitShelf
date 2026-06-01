INSERT INTO document_ingest_scope_overrides (
    source_path,
    entity_id,
    is_global,
    created_by_user_id,
    updated_at
)
VALUES (%s, %s, %s, %s, now())
ON CONFLICT (source_path) DO UPDATE SET
    entity_id = EXCLUDED.entity_id,
    is_global = EXCLUDED.is_global,
    created_by_user_id = EXCLUDED.created_by_user_id,
    updated_at = now()
RETURNING source_path, entity_id, is_global, created_by_user_id;
