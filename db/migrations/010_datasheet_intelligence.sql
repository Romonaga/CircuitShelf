BEGIN;

CREATE TABLE IF NOT EXISTS document_intelligence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
    component_name text,
    component_type text NOT NULL DEFAULT 'component',
    summary text NOT NULL DEFAULT '',
    confidence numeric(6, 4) NOT NULL DEFAULT 0.0000,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_intelligence_facts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    intelligence_id uuid NOT NULL REFERENCES document_intelligence(id) ON DELETE CASCADE,
    fact_type text NOT NULL,
    label text NOT NULL,
    value text NOT NULL,
    unit text,
    page_number integer,
    source_chunk_index integer,
    evidence text,
    confidence numeric(6, 4) NOT NULL DEFAULT 0.0000,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_intelligence_facts_lookup_idx
    ON document_intelligence_facts (intelligence_id, fact_type);

CREATE TABLE IF NOT EXISTS document_intelligence_pins (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    intelligence_id uuid NOT NULL REFERENCES document_intelligence(id) ON DELETE CASCADE,
    pin_number integer NOT NULL,
    label text NOT NULL,
    function_text text NOT NULL,
    page_number integer,
    source_chunk_index integer,
    evidence text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (intelligence_id, pin_number)
);

INSERT INTO schema_migrations (version, name)
VALUES (10, 'datasheet_intelligence')
ON CONFLICT (version) DO NOTHING;

COMMIT;
