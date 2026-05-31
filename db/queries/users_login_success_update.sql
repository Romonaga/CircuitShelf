UPDATE users
SET failed_login_count = 0,
    last_login_at = now(),
    updated_at = now()
WHERE id = %s;
