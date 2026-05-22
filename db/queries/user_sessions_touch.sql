UPDATE user_sessions
SET last_seen_at = now(),
    expires_at = now() + (%s || ' seconds')::interval
WHERE token_hash = %s;
