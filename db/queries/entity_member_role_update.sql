UPDATE entity_memberships em
SET role_id = er.id,
    is_active = true,
    updated_at = now()
FROM entity_roles er
WHERE em.entity_id = %s
  AND em.user_id = %s
  AND er.code = %s
RETURNING em.entity_id, em.user_id, er.code AS role_code, er.display_name AS role_name, er.can_manage_entity;
