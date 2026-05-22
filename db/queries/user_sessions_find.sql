SELECT u.id,
       u.username,
       u.is_admin
FROM user_sessions s
JOIN users u ON u.id = s.user_id
WHERE s.token_hash = %s
  AND s.expires_at > now()
  AND u.is_active = true;
