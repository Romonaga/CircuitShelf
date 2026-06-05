BEGIN;

ALTER TABLE conversation_turns
    ADD COLUMN IF NOT EXISTS response_snapshot jsonb;

INSERT INTO schema_migrations (version, name)
VALUES (41, 'conversation_turn_response_snapshot')
ON CONFLICT (version) DO NOTHING;

COMMIT;
