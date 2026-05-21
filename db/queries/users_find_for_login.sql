SELECT username, password_hash, is_admin
FROM active_login_users
WHERE username = %s;
