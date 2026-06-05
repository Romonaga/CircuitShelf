BEGIN;

UPDATE ai_assist_events ev
SET decision_reason = CASE
    WHEN task.code = 'answer_validation' AND ev.context_type = 'conversation'
        THEN 'Answer validation ran according to the configured OpenAI assist and response-finalizer policy.'
    WHEN task.code = 'answer_validation'
        THEN 'OpenAI assist ran because the configured answer-assist policy allowed it.'
    WHEN task.code = 'ingestion_assist' AND ev.context_type = 'datasheet_intelligence'
        THEN 'Datasheet intelligence repair ran because deterministic extraction needed pinout, fact, confidence, or gap repair.'
    WHEN task.code = 'ingestion_assist' AND ev.context_type = 'document_ingest'
        THEN 'Ingestion review ran because document-level OpenAI ingestion assist was enabled.'
    WHEN task.code = 'inventory_photo_import'
        THEN 'User requested inventory import from a photo.'
    ELSE 'OpenAI assist ran for the recorded task and context.'
END
FROM ai_task_types task
WHERE task.id = ev.task_type_id
  AND nullif(ev.decision_reason, '') IS NULL;

INSERT INTO schema_migrations (version, name)
VALUES (39, 'ai_assist_decision_backfill')
ON CONFLICT (version) DO NOTHING;

COMMIT;
