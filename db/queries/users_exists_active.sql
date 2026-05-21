SELECT EXISTS (
    SELECT 1
    FROM users
    WHERE is_active = true
) AS has_users;
