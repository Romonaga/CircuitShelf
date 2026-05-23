SELECT id, username, password_hash, is_admin
FROM users
WHERE id = %s
  AND is_active = true;
