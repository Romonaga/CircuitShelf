UPDATE user_sessions
SET last_seen_at = now()
WHERE token_hash = %s;
