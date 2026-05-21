SELECT s.username,
       u.is_admin
FROM user_sessions s
JOIN users u ON u.username = s.username
WHERE s.token_hash = %s
  AND s.expires_at > now()
  AND u.is_active = true;
