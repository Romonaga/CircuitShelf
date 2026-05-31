SELECT id,
       username,
       password_hash,
       is_admin,
       can_manage_system,
       force_password_change,
       password_changed_at,
       failed_login_count,
       is_active,
       disabled_at,
       disabled_reason
FROM users
WHERE username = %s;
