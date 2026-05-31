BEGIN;

CREATE TABLE IF NOT EXISTS user_types (
    id smallserial PRIMARY KEY,
    code text NOT NULL UNIQUE,
    display_name text NOT NULL,
    description text NOT NULL DEFAULT ''
);

INSERT INTO user_types (id, code, display_name, description)
VALUES
    (1, 'standard', 'Standard User', 'Regular application user.'),
    (2, 'system_admin', 'System Admin', 'Can manage system-level settings and global corpus operations.')
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description;

SELECT setval('user_types_id_seq', GREATEST((SELECT coalesce(max(id), 1) FROM user_types), 1), true);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS user_type_id smallint REFERENCES user_types(id),
    ADD COLUMN IF NOT EXISTS can_manage_system boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS email citext UNIQUE,
    ADD COLUMN IF NOT EXISTS display_name text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS nickname text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS phone text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS address text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS password_changed_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS force_password_change boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS failed_login_count integer NOT NULL DEFAULT 0 CHECK (failed_login_count >= 0),
    ADD COLUMN IF NOT EXISTS disabled_at timestamptz,
    ADD COLUMN IF NOT EXISTS disabled_reason text;

UPDATE users
   SET can_manage_system = true,
       user_type_id = 2
 WHERE is_admin = true;

UPDATE users
   SET user_type_id = 1
 WHERE user_type_id IS NULL;

ALTER TABLE users
    ALTER COLUMN user_type_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS users_user_type_idx ON users (user_type_id);
CREATE INDEX IF NOT EXISTS users_can_manage_system_idx ON users (can_manage_system) WHERE can_manage_system = true;

DROP VIEW IF EXISTS active_login_users;

CREATE VIEW active_login_users AS
SELECT id,
       username,
       password_hash,
       is_admin,
       can_manage_system,
       force_password_change
FROM users
WHERE is_active = true
  AND disabled_at IS NULL;

CREATE TABLE IF NOT EXISTS entity_roles (
    id smallserial PRIMARY KEY,
    code text NOT NULL UNIQUE,
    display_name text NOT NULL,
    can_manage_entity boolean NOT NULL DEFAULT false,
    sort_order integer NOT NULL DEFAULT 100
);

INSERT INTO entity_roles (id, code, display_name, can_manage_entity, sort_order)
VALUES
    (1, 'owner', 'Owner', true, 10),
    (2, 'admin', 'Admin', true, 20),
    (3, 'user', 'User', false, 30)
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    display_name = EXCLUDED.display_name,
    can_manage_entity = EXCLUDED.can_manage_entity,
    sort_order = EXCLUDED.sort_order;

SELECT setval('entity_roles_id_seq', GREATEST((SELECT coalesce(max(id), 1) FROM entity_roles), 1), true);

CREATE TABLE IF NOT EXISTS entities (
    id bigserial PRIMARY KEY,
    name text NOT NULL,
    slug text NOT NULL UNIQUE,
    owner_user_id bigint REFERENCES users(id) ON DELETE SET NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name)
);

CREATE INDEX IF NOT EXISTS entities_owner_idx ON entities (owner_user_id);
CREATE INDEX IF NOT EXISTS entities_active_idx ON entities (is_active) WHERE is_active = true;

CREATE TABLE IF NOT EXISTS entity_memberships (
    entity_id bigint NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id smallint NOT NULL REFERENCES entity_roles(id),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, user_id)
);

CREATE INDEX IF NOT EXISTS entity_memberships_user_idx ON entity_memberships (user_id, is_active);
CREATE INDEX IF NOT EXISTS entity_memberships_role_idx ON entity_memberships (role_id);

CREATE TABLE IF NOT EXISTS password_policies (
    id bigserial PRIMARY KEY,
    entity_id bigint REFERENCES entities(id) ON DELETE CASCADE,
    min_length integer NOT NULL DEFAULT 12 CHECK (min_length BETWEEN 8 AND 128),
    require_upper boolean NOT NULL DEFAULT true,
    require_lower boolean NOT NULL DEFAULT true,
    require_number boolean NOT NULL DEFAULT true,
    require_symbol boolean NOT NULL DEFAULT false,
    password_change_days integer NOT NULL DEFAULT 0 CHECK (password_change_days >= 0),
    max_failed_attempts integer NOT NULL DEFAULT 5 CHECK (max_failed_attempts BETWEEN 1 AND 100),
    lockout_minutes integer NOT NULL DEFAULT 30 CHECK (lockout_minutes >= 0),
    updated_by bigint REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT password_policies_one_system_default UNIQUE NULLS NOT DISTINCT (entity_id)
);

INSERT INTO password_policies (entity_id)
VALUES (NULL)
ON CONFLICT (entity_id) DO NOTHING;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS entity_id bigint REFERENCES entities(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS is_global boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS created_by_user_id bigint REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS documents_scope_idx ON documents (is_global, entity_id, status);
CREATE INDEX IF NOT EXISTS documents_entity_idx ON documents (entity_id) WHERE entity_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS ai_provider_types (
    id smallserial PRIMARY KEY,
    code text NOT NULL UNIQUE,
    display_name text NOT NULL
);

INSERT INTO ai_provider_types (id, code, display_name)
VALUES
    (1, 'openai', 'OpenAI'),
    (2, 'ollama', 'Ollama')
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    display_name = EXCLUDED.display_name;

SELECT setval('ai_provider_types_id_seq', GREATEST((SELECT coalesce(max(id), 1) FROM ai_provider_types), 1), true);

CREATE TABLE IF NOT EXISTS ai_key_policies (
    id smallserial PRIMARY KEY,
    code text NOT NULL UNIQUE,
    display_name text NOT NULL,
    description text NOT NULL DEFAULT ''
);

INSERT INTO ai_key_policies (id, code, display_name, description)
VALUES
    (1, 'entity', 'Entity key', 'Use the entity-owned provider key.'),
    (2, 'user_when_available', 'User key when available', 'Use the user key first, then entity/system fallback.'),
    (3, 'user_only', 'User key only', 'Use only the user-owned provider key.'),
    (4, 'system', 'System key', 'Use the system-owned provider key.')
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description;

CREATE TABLE IF NOT EXISTS ai_assist_modes (
    id smallserial PRIMARY KEY,
    code text NOT NULL UNIQUE,
    display_name text NOT NULL,
    description text NOT NULL DEFAULT ''
);

INSERT INTO ai_assist_modes (id, code, display_name, description)
VALUES
    (1, 'off', 'Off', 'Never call this provider for assist work.'),
    (2, 'auto', 'Auto', 'Use deterministic rules to decide when provider assist is useful.'),
    (3, 'always', 'Always', 'Call this provider whenever the workflow supports assist.')
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description;

CREATE TABLE IF NOT EXISTS ai_task_types (
    id smallserial PRIMARY KEY,
    code text NOT NULL UNIQUE,
    display_name text NOT NULL,
    description text NOT NULL DEFAULT ''
);

INSERT INTO ai_task_types (id, code, display_name, description)
VALUES
    (1, 'answer_validation', 'Answer validation', 'Validate and improve local RAG answers.'),
    (2, 'bench_plan', 'Bench plan', 'Create or validate assembly plans.'),
    (3, 'ingestion_assist', 'Ingestion assist', 'Assist with document extraction, chunking, or metadata.'),
    (4, 'project_finder', 'Project finder', 'Improve project candidate extraction and grouping.'),
    (5, 'photo_check', 'Photo check', 'Assist with bench photo review.')
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description;

CREATE TABLE IF NOT EXISTS ai_model_pricing (
    id bigserial PRIMARY KEY,
    provider_type_id smallint NOT NULL REFERENCES ai_provider_types(id),
    model_name text NOT NULL,
    input_per_million numeric(12, 6) NOT NULL DEFAULT 0,
    cached_input_per_million numeric(12, 6) NOT NULL DEFAULT 0,
    output_per_million numeric(12, 6) NOT NULL DEFAULT 0,
    currency text NOT NULL DEFAULT 'USD',
    is_active boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider_type_id, model_name)
);

INSERT INTO ai_model_pricing (
    provider_type_id,
    model_name,
    input_per_million,
    cached_input_per_million,
    output_per_million
)
SELECT p.id, v.model_name, v.input_rate, v.cached_rate, v.output_rate
FROM ai_provider_types p
CROSS JOIN (
    VALUES
        ('gpt-5.5', 5.00::numeric, 0.50::numeric, 30.00::numeric),
        ('gpt-5.4', 2.50::numeric, 0.25::numeric, 15.00::numeric),
        ('gpt-5.4-mini', 0.75::numeric, 0.075::numeric, 4.50::numeric),
        ('gpt-5-chat-latest', 1.25::numeric, 0.125::numeric, 10.00::numeric)
) AS v(model_name, input_rate, cached_rate, output_rate)
WHERE p.code = 'openai'
ON CONFLICT (provider_type_id, model_name) DO UPDATE SET
    input_per_million = EXCLUDED.input_per_million,
    cached_input_per_million = EXCLUDED.cached_input_per_million,
    output_per_million = EXCLUDED.output_per_million,
    updated_at = now();

CREATE TABLE IF NOT EXISTS system_ai_provider_settings (
    provider_type_id smallint PRIMARY KEY REFERENCES ai_provider_types(id),
    enabled boolean NOT NULL DEFAULT false,
    encrypted_api_key text NOT NULL DEFAULT '',
    key_preview text NOT NULL DEFAULT '',
    assist_mode_id smallint NOT NULL DEFAULT 2 REFERENCES ai_assist_modes(id),
    default_model text NOT NULL DEFAULT '',
    updated_by bigint REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entity_ai_provider_settings (
    entity_id bigint NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    provider_type_id smallint NOT NULL REFERENCES ai_provider_types(id),
    enabled boolean NOT NULL DEFAULT false,
    encrypted_api_key text NOT NULL DEFAULT '',
    key_preview text NOT NULL DEFAULT '',
    key_policy_id smallint NOT NULL DEFAULT 1 REFERENCES ai_key_policies(id),
    assist_mode_id smallint NOT NULL DEFAULT 2 REFERENCES ai_assist_modes(id),
    default_model text NOT NULL DEFAULT '',
    monthly_budget numeric(12, 4) NOT NULL DEFAULT 0,
    warn_percent integer NOT NULL DEFAULT 80 CHECK (warn_percent BETWEEN 1 AND 100),
    stop_percent integer NOT NULL DEFAULT 100 CHECK (stop_percent BETWEEN 1 AND 100),
    updated_by bigint REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, provider_type_id)
);

CREATE TABLE IF NOT EXISTS user_ai_provider_settings (
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider_type_id smallint NOT NULL REFERENCES ai_provider_types(id),
    enabled boolean NOT NULL DEFAULT false,
    encrypted_api_key text NOT NULL DEFAULT '',
    key_preview text NOT NULL DEFAULT '',
    key_policy_id smallint NOT NULL DEFAULT 2 REFERENCES ai_key_policies(id),
    assist_mode_id smallint NOT NULL DEFAULT 2 REFERENCES ai_assist_modes(id),
    default_model text NOT NULL DEFAULT '',
    monthly_budget numeric(12, 4) NOT NULL DEFAULT 0,
    warn_percent integer NOT NULL DEFAULT 80 CHECK (warn_percent BETWEEN 1 AND 100),
    stop_percent integer NOT NULL DEFAULT 100 CHECK (stop_percent BETWEEN 1 AND 100),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, provider_type_id)
);

CREATE TABLE IF NOT EXISTS ai_assist_events (
    id bigserial PRIMARY KEY,
    entity_id bigint REFERENCES entities(id) ON DELETE SET NULL,
    user_id bigint REFERENCES users(id) ON DELETE SET NULL,
    provider_type_id smallint REFERENCES ai_provider_types(id) ON DELETE SET NULL,
    task_type_id smallint REFERENCES ai_task_types(id) ON DELETE SET NULL,
    model_name text NOT NULL DEFAULT '',
    context_type text NOT NULL DEFAULT '',
    context_id uuid,
    round_number integer NOT NULL DEFAULT 1,
    round_count integer NOT NULL DEFAULT 1,
    input_tokens integer NOT NULL DEFAULT 0,
    cached_input_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    estimated_cost numeric(14, 8) NOT NULL DEFAULT 0,
    paid_by text NOT NULL DEFAULT 'unknown' CHECK (paid_by IN ('system', 'entity', 'user', 'unknown')),
    provider_key_owner_user_id bigint REFERENCES users(id) ON DELETE SET NULL,
    success boolean NOT NULL DEFAULT true,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_assist_events_entity_created_idx ON ai_assist_events (entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_assist_events_user_created_idx ON ai_assist_events (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_assist_events_task_idx ON ai_assist_events (task_type_id, created_at DESC);

INSERT INTO schema_migrations (version, name)
VALUES (20, 'entities_security_and_ai_foundation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
