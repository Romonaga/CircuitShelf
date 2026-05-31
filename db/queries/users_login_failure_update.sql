UPDATE users
SET failed_login_count = failed_login_count + 1,
    disabled_at = CASE
        WHEN failed_login_count + 1 >= %s THEN now()
        ELSE disabled_at
    END,
    disabled_reason = CASE
        WHEN failed_login_count + 1 >= %s THEN 'Too many failed login attempts.'
        ELSE disabled_reason
    END,
    updated_at = now()
WHERE id = %s
RETURNING failed_login_count, disabled_at, disabled_reason;
