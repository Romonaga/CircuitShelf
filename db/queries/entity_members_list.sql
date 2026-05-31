SELECT u.id AS user_id,
       u.username,
       u.email,
       u.display_name,
       u.nickname,
       u.is_active,
       u.can_manage_system,
       er.code AS role_code,
       er.display_name AS role_name,
       er.can_manage_entity,
       em.created_at,
       em.updated_at
FROM entity_memberships em
JOIN users u ON u.id = em.user_id
JOIN entity_roles er ON er.id = em.role_id
WHERE em.entity_id = %s
  AND em.is_active = true
ORDER BY er.sort_order, u.username;
