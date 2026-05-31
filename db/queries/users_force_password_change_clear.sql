UPDATE users
SET force_password_change = false,
    password_changed_at = now(),
    updated_at = now()
WHERE id = %s;
