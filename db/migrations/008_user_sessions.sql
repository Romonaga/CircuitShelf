BEGIN;

CREATE TABLE IF NOT EXISTS user_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username citext NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS user_sessions_username_idx
    ON user_sessions (username);

CREATE INDEX IF NOT EXISTS user_sessions_expires_idx
    ON user_sessions (expires_at);

INSERT INTO schema_migrations (version, name)
VALUES (8, 'user_sessions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
