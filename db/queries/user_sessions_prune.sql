DELETE FROM user_sessions
WHERE expires_at <= now();
