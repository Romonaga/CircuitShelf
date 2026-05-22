CREATE TABLE IF NOT EXISTS conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username citext REFERENCES users(username) ON DELETE SET NULL,
    title text NOT NULL,
    archived_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversations_user_updated_idx
    ON conversations (username, updated_at DESC)
    WHERE archived_at IS NULL;

CREATE TABLE IF NOT EXISTS conversation_turns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    ordinal integer NOT NULL,
    question text NOT NULL,
    answer_markdown text NOT NULL,
    model_name text,
    retrieval_strategy text,
    confidence_score numeric(6, 4),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (conversation_id, ordinal)
);

CREATE INDEX IF NOT EXISTS conversation_turns_conversation_ordinal_idx
    ON conversation_turns (conversation_id, ordinal);

INSERT INTO schema_migrations (version, name)
VALUES (15, 'conversations')
ON CONFLICT (version) DO NOTHING;
