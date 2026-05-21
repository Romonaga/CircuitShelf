INSERT INTO user_sessions (
    username,
    token_hash,
    expires_at
)
VALUES (%s, %s, now() + (%s || ' seconds')::interval);
