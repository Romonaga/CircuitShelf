UPDATE users
SET password_hash = %s,
    force_password_change = %s,
    failed_login_count = 0,
    disabled_at = NULL,
    disabled_reason = NULL,
    password_changed_at = now(),
    updated_at = now()
WHERE id = %s
RETURNING id, username, force_password_change, updated_at;
