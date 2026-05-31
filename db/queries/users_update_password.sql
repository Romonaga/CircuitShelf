UPDATE users
SET password_hash = %s,
    force_password_change = false,
    password_changed_at = now(),
    updated_at = now()
WHERE id = %s
  AND is_active = true;
