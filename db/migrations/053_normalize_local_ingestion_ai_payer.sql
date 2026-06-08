BEGIN;

UPDATE ai_assist_events
   SET paid_by = 'system'
 WHERE paid_by = 'local';

ALTER TABLE ai_assist_events
    DROP CONSTRAINT IF EXISTS ai_assist_events_paid_by_check;

ALTER TABLE ai_assist_events
    ADD CONSTRAINT ai_assist_events_paid_by_check
    CHECK (paid_by IN ('system', 'entity', 'user', 'unknown'));

INSERT INTO schema_migrations (version, name)
VALUES (53, 'normalize_local_ingestion_ai_payer')
ON CONFLICT (version) DO NOTHING;

COMMIT;
