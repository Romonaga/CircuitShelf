BEGIN;

CREATE TABLE IF NOT EXISTS lab_locations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    display_name text NOT NULL,
    normalized_name text NOT NULL,
    notes text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, normalized_name)
);

ALTER TABLE lab_parts
    ADD COLUMN IF NOT EXISTS location_id uuid REFERENCES lab_locations(id) ON DELETE SET NULL;

INSERT INTO lab_locations (user_id, display_name, normalized_name, updated_at)
SELECT DISTINCT
       p.user_id,
       trim(p.location),
       trim(regexp_replace(regexp_replace(lower(trim(p.location)), '[^a-z0-9]+', ' ', 'g'), ' +', ' ', 'g')),
       now()
FROM lab_parts p
WHERE trim(coalesce(p.location, '')) <> ''
ON CONFLICT (user_id, normalized_name) DO NOTHING;

UPDATE lab_parts p
SET location_id = l.id
FROM lab_locations l
WHERE p.location_id IS NULL
  AND trim(coalesce(p.location, '')) <> ''
  AND l.user_id = p.user_id
  AND l.normalized_name = trim(regexp_replace(regexp_replace(lower(trim(p.location)), '[^a-z0-9]+', ' ', 'g'), ' +', ' ', 'g'));

CREATE INDEX IF NOT EXISTS lab_locations_user_name_idx
    ON lab_locations (user_id, normalized_name);

CREATE INDEX IF NOT EXISTS lab_parts_location_id_idx
    ON lab_parts (location_id)
    WHERE location_id IS NOT NULL;

INSERT INTO schema_migrations (version, name)
VALUES (35, 'lab_inventory_locations')
ON CONFLICT (version) DO NOTHING;

COMMIT;
