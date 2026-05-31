SELECT e.id AS entity_id
FROM entity_memberships em
JOIN entities e ON e.id = em.entity_id
JOIN entity_roles er ON er.id = em.role_id
WHERE em.user_id = %s
  AND em.is_active = true
  AND e.is_active = true
ORDER BY er.sort_order, e.name
LIMIT 1;
