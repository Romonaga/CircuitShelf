SELECT e.id AS entity_id,
       e.name AS entity_name,
       e.slug AS entity_slug,
       e.owner_user_id,
       er.code AS role_code,
       er.display_name AS role_name,
       er.can_manage_entity
FROM entity_memberships em
JOIN entities e ON e.id = em.entity_id
JOIN entity_roles er ON er.id = em.role_id
WHERE em.user_id = %s
  AND em.is_active = true
  AND e.is_active = true
ORDER BY er.sort_order, e.name
LIMIT 1;
