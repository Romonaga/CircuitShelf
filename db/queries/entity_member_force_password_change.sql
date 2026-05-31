UPDATE users u
SET force_password_change = %s,
    updated_at = now()
FROM entity_memberships em
WHERE em.user_id = u.id
  AND em.entity_id = %s
  AND u.id = %s
  AND em.is_active = true
RETURNING u.id AS user_id, u.username, u.force_password_change;
