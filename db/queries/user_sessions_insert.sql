INSERT INTO user_sessions (
    user_id,
    username,
    token_hash,
    expires_at
)
VALUES (%s, %s, %s, now() + (%s || ' seconds')::interval);
