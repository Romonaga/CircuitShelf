UPDATE users
SET last_login_at = now(),
    updated_at = now()
WHERE username = %s;
