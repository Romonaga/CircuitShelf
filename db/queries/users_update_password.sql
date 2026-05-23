UPDATE users
SET password_hash = %s,
    updated_at = now()
WHERE id = %s
  AND is_active = true;
