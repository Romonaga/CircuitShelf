INSERT INTO users (
    username,
    password_hash,
    is_admin,
    is_active,
    email,
    display_name,
    nickname,
    phone,
    address,
    force_password_change,
    password_changed_at
)
VALUES (
    %s,
    %s,
    %s,
    true,
    nullif(%s, '')::citext,
    %s,
    %s,
    %s,
    %s,
    %s,
    now()
)
RETURNING id,
          username,
          email,
          display_name,
          nickname,
          phone,
          address,
          is_admin,
          is_active,
          can_manage_system,
          force_password_change,
          created_at,
          updated_at;
