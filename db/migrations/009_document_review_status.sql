BEGIN;

ALTER TABLE documents
    DROP CONSTRAINT IF EXISTS documents_status_check;

ALTER TABLE documents
    ADD CONSTRAINT documents_status_check
    CHECK (status IN ('pending', 'needs_review', 'indexed', 'failed', 'removed'));

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS reviewed_at timestamptz,
    ADD COLUMN IF NOT EXISTS reviewed_by citext REFERENCES users(username) ON DELETE SET NULL;

INSERT INTO schema_migrations (version, name)
VALUES (9, 'document_review_status')
ON CONFLICT (version) DO NOTHING;

COMMIT;
