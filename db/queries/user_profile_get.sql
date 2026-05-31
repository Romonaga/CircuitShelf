SELECT id,
       username,
       email,
       display_name,
       nickname,
       phone,
       address,
       is_admin,
       can_manage_system,
       force_password_change,
       password_changed_at,
       last_login_at
FROM users
WHERE id = %s;
