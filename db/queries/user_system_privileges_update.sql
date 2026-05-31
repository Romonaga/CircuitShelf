UPDATE users
SET can_manage_system = %s,
    is_admin = %s,
    user_type_id = CASE WHEN %s THEN 2 ELSE 1 END,
    updated_at = now()
WHERE username = %s
RETURNING id, username, is_admin, can_manage_system;
