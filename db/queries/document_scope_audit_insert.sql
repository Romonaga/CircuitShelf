INSERT INTO document_scope_audit (
    source_path,
    previous_is_global,
    previous_entity_id,
    new_is_global,
    new_entity_id,
    changed_by_user_id,
    reason
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id;
