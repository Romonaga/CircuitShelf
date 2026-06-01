UPDATE users u
SET failed_login_count = 0,
    disabled_at = NULL,
    disabled_reason = NULL,
    is_active = true,
    updated_at = now()
FROM entity_memberships em
WHERE em.user_id = u.id
  AND em.entity_id = %s
  AND u.id = %s
  AND em.is_active = true
RETURNING u.id AS user_id, u.username;
