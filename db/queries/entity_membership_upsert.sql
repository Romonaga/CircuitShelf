INSERT INTO entity_memberships (entity_id, user_id, role_id, is_active)
SELECT %s, %s, er.id, true
FROM entity_roles er
WHERE er.code = %s
ON CONFLICT (entity_id, user_id) DO UPDATE SET
    role_id = EXCLUDED.role_id,
    is_active = true,
    updated_at = now()
RETURNING entity_id, user_id, role_id, is_active, created_at, updated_at;
