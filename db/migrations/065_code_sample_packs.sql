BEGIN;

CREATE TABLE IF NOT EXISTS code_sample_packs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_key text NOT NULL UNIQUE,
    display_name text NOT NULL,
    root_path text NOT NULL DEFAULT '',
    summary text NOT NULL DEFAULT '',
    board text NOT NULL DEFAULT '',
    framework text NOT NULL DEFAULT '',
    languages text[] NOT NULL DEFAULT '{}',
    libraries text[] NOT NULL DEFAULT '{}',
    components text[] NOT NULL DEFAULT '{}',
    interfaces text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS code_sample_files (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_id uuid NOT NULL REFERENCES code_sample_packs(id) ON DELETE CASCADE,
    document_id uuid NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
    relative_path text NOT NULL,
    language text NOT NULL DEFAULT '',
    role text NOT NULL DEFAULT '',
    board text NOT NULL DEFAULT '',
    framework text NOT NULL DEFAULT '',
    libraries text[] NOT NULL DEFAULT '{}',
    components text[] NOT NULL DEFAULT '{}',
    interfaces text[] NOT NULL DEFAULT '{}',
    pins jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pack_id, relative_path)
);

CREATE INDEX IF NOT EXISTS code_sample_files_document_idx
    ON code_sample_files (document_id);

CREATE INDEX IF NOT EXISTS code_sample_files_relative_path_idx
    ON code_sample_files (relative_path);

CREATE INDEX IF NOT EXISTS code_sample_packs_components_idx
    ON code_sample_packs USING gin (components);

CREATE INDEX IF NOT EXISTS code_sample_packs_interfaces_idx
    ON code_sample_packs USING gin (interfaces);

INSERT INTO schema_migrations (version, name)
VALUES (65, 'code_sample_packs')
ON CONFLICT (version) DO NOTHING;

COMMIT;
