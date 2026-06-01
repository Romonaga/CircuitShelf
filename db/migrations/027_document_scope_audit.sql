BEGIN;

CREATE TABLE IF NOT EXISTS document_scope_audit (
    id bigserial PRIMARY KEY,
    source_path text NOT NULL,
    previous_is_global boolean,
    previous_entity_id bigint REFERENCES entities(id) ON DELETE SET NULL,
    new_is_global boolean NOT NULL,
    new_entity_id bigint REFERENCES entities(id) ON DELETE SET NULL,
    changed_by_user_id bigint REFERENCES users(id) ON DELETE SET NULL,
    reason text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_scope_audit_source_created_idx
    ON document_scope_audit (source_path, created_at DESC);

CREATE INDEX IF NOT EXISTS document_scope_audit_actor_created_idx
    ON document_scope_audit (changed_by_user_id, created_at DESC)
    WHERE changed_by_user_id IS NOT NULL;

INSERT INTO schema_migrations (version, name)
VALUES (27, 'document_scope_audit')
ON CONFLICT (version) DO NOTHING;

COMMIT;
