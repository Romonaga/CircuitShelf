SELECT a.id,
       a.source_path,
       a.previous_is_global,
       a.previous_entity_id,
       pe.name AS previous_entity_name,
       a.new_is_global,
       a.new_entity_id,
       ne.name AS new_entity_name,
       a.changed_by_user_id,
       u.username AS changed_by_username,
       a.reason,
       a.created_at
FROM document_scope_audit a
LEFT JOIN entities pe ON pe.id = a.previous_entity_id
LEFT JOIN entities ne ON ne.id = a.new_entity_id
LEFT JOIN users u ON u.id = a.changed_by_user_id
WHERE a.source_path = %s
ORDER BY a.created_at DESC
LIMIT %s;
