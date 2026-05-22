BEGIN;

CREATE TABLE IF NOT EXISTS lab_parts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    display_name text NOT NULL,
    normalized_name text NOT NULL,
    part_type text NOT NULL DEFAULT 'component',
    quantity integer NOT NULL DEFAULT 1 CHECK (quantity >= 0),
    location text NOT NULL DEFAULT '',
    notes text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, normalized_name)
);

CREATE TABLE IF NOT EXISTS lab_part_aliases (
    id bigserial PRIMARY KEY,
    part_id uuid NOT NULL REFERENCES lab_parts(id) ON DELETE CASCADE,
    alias text NOT NULL,
    normalized_alias text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (part_id, normalized_alias)
);

CREATE INDEX IF NOT EXISTS lab_parts_user_type_idx
    ON lab_parts (user_id, part_type, display_name);

CREATE INDEX IF NOT EXISTS lab_part_aliases_lookup_idx
    ON lab_part_aliases (normalized_alias);

INSERT INTO schema_migrations (version, name)
VALUES (17, 'lab_inventory')
ON CONFLICT (version) DO NOTHING;

COMMIT;
