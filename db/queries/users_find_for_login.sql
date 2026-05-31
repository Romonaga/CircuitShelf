SELECT id,
       username,
       password_hash,
       is_admin,
       can_manage_system,
       force_password_change
FROM active_login_users
WHERE username = %s;
