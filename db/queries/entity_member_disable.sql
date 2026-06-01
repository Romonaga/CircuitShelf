UPDATE users u
SET failed_login_count = 0,
    disabled_at = now(),
    disabled_reason = %s,
    updated_at = now()
FROM entity_memberships em
WHERE em.user_id = u.id
  AND em.entity_id = %s
  AND u.id = %s
  AND em.is_active = true
RETURNING u.id AS user_id, u.username, u.disabled_at, u.disabled_reason;
