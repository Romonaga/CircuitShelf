INSERT INTO users (username, password_hash, is_admin, is_active)
VALUES (%s, %s, %s, %s)
ON CONFLICT (username) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    is_admin = EXCLUDED.is_admin,
    is_active = EXCLUDED.is_active,
    updated_at = now();
