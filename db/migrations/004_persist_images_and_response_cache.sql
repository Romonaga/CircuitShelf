BEGIN;

ALTER TABLE document_images
    ADD COLUMN IF NOT EXISTS image_bytes bytea,
    ADD COLUMN IF NOT EXISTS image_mime_type text NOT NULL DEFAULT 'image/png';

ALTER TABLE response_cache_sources
    ADD COLUMN IF NOT EXISTS chunk_index integer,
    ADD COLUMN IF NOT EXISTS section_title text,
    ADD COLUMN IF NOT EXISTS category text,
    ADD COLUMN IF NOT EXISTS source_image_key text;

CREATE TABLE IF NOT EXISTS response_cache_chat_turns (
    cache_entry_id uuid NOT NULL REFERENCES response_cache_entries(id) ON DELETE CASCADE,
    turn_index integer NOT NULL,
    user_message text NOT NULL,
    assistant_message text NOT NULL,
    PRIMARY KEY (cache_entry_id, turn_index)
);

CREATE INDEX IF NOT EXISTS document_images_document_idx
    ON document_images (document_id, image_ordinal);

CREATE INDEX IF NOT EXISTS response_cache_entries_accessed_idx
    ON response_cache_entries (last_accessed_at);

INSERT INTO schema_migrations (version, name)
VALUES (4, 'persist_images_and_response_cache')
ON CONFLICT (version) DO NOTHING;

COMMIT;
