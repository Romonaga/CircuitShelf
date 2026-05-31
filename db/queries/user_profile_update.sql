UPDATE users
SET email = nullif(%s, ''),
    display_name = %s,
    nickname = %s,
    phone = %s,
    address = %s,
    updated_at = now()
WHERE id = %s
RETURNING id,
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
          last_login_at;
