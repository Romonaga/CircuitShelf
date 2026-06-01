BEGIN;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS entity_id bigint REFERENCES entities(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS is_global boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS created_by_user_id bigint REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS documents_scope_idx ON documents (is_global, entity_id, status);
CREATE INDEX IF NOT EXISTS documents_entity_idx ON documents (entity_id) WHERE entity_id IS NOT NULL;

CREATE OR REPLACE FUNCTION document_visible_to_entity(
    p_is_global boolean,
    p_entity_id bigint,
    p_active_entity_id bigint
) RETURNS boolean
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT coalesce(p_is_global, false)
        OR (
            p_active_entity_id IS NOT NULL
            AND p_entity_id = p_active_entity_id
        );
$$;

INSERT INTO schema_migrations (version, name)
VALUES (24, 'document_visibility_scope')
ON CONFLICT (version) DO NOTHING;

COMMIT;
