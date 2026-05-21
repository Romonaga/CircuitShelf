BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_settings (
    key text PRIMARY KEY,
    value_type text NOT NULL CHECK (value_type IN ('text', 'integer', 'numeric', 'boolean')),
    text_value text,
    integer_value bigint,
    numeric_value numeric,
    boolean_value boolean,
    description text,
    is_sensitive boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(text_value, integer_value, numeric_value, boolean_value) = 1),
    CHECK (
        (value_type = 'text' AND text_value IS NOT NULL)
        OR (value_type = 'integer' AND integer_value IS NOT NULL)
        OR (value_type = 'numeric' AND numeric_value IS NOT NULL)
        OR (value_type = 'boolean' AND boolean_value IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS llm_models (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name text NOT NULL UNIQUE,
    display_name text NOT NULL,
    provider text NOT NULL DEFAULT 'ollama',
    is_default boolean NOT NULL DEFAULT false,
    is_enabled boolean NOT NULL DEFAULT true,
    temperature numeric(4, 3) NOT NULL DEFAULT 0.200,
    num_predict integer NOT NULL DEFAULT 3072,
    num_ctx integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS llm_models_one_default_idx
    ON llm_models (is_default)
    WHERE is_default;

CREATE TABLE IF NOT EXISTS query_synonyms (
    id bigserial PRIMARY KEY,
    canonical_term text NOT NULL,
    synonym text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (canonical_term, synonym)
);

CREATE TABLE IF NOT EXISTS prompt_security_banned_phrases (
    id bigserial PRIMARY KEY,
    phrase text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rerank_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    weight_faiss numeric(5, 4) NOT NULL,
    weight_rerank numeric(5, 4) NOT NULL,
    is_default boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS rerank_profiles_one_default_idx
    ON rerank_profiles (is_default)
    WHERE is_default;

CREATE TABLE IF NOT EXISTS rerank_profile_keywords (
    profile_id uuid NOT NULL REFERENCES rerank_profiles(id) ON DELETE CASCADE,
    keyword text NOT NULL,
    weight numeric(5, 4) NOT NULL DEFAULT 1.0000,
    PRIMARY KEY (profile_id, keyword)
);

CREATE TABLE IF NOT EXISTS chunk_categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    detail_level text NOT NULL,
    priority numeric(6, 4) NOT NULL DEFAULT 0.0000
);

CREATE TABLE IF NOT EXISTS chunk_category_keywords (
    category_id uuid NOT NULL REFERENCES chunk_categories(id) ON DELETE CASCADE,
    keyword text NOT NULL,
    PRIMARY KEY (category_id, keyword)
);

CREATE TABLE IF NOT EXISTS equation_patterns (
    id bigserial PRIMARY KEY,
    pattern_type text NOT NULL CHECK (pattern_type IN ('symbol', 'keyword', 'ocr_caption_keyword', 'variable_definition')),
    pattern text NOT NULL,
    is_regex boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pattern_type, pattern)
);

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username citext NOT NULL UNIQUE,
    password_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    is_admin boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz
);

CREATE OR REPLACE VIEW active_login_users AS
SELECT username, password_hash, is_admin
FROM users
WHERE is_active = true;

CREATE TABLE IF NOT EXISTS ingest_runs (
    id bigserial PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    added_count integer NOT NULL DEFAULT 0,
    modified_count integer NOT NULL DEFAULT 0,
    removed_count integer NOT NULL DEFAULT 0,
    skipped_count integer NOT NULL DEFAULT 0,
    chunk_count integer NOT NULL DEFAULT 0,
    embedding_count integer NOT NULL DEFAULT 0,
    image_count integer NOT NULL DEFAULT 0,
    error_message text
);

CREATE TABLE IF NOT EXISTS documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_path text NOT NULL UNIQUE,
    display_name text NOT NULL,
    file_extension text NOT NULL,
    size_bytes bigint NOT NULL,
    mtime_ns bigint NOT NULL,
    sha256 text,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'indexed', 'failed', 'removed')),
    page_count integer,
    last_ingested_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingest_run_documents (
    run_id bigint NOT NULL REFERENCES ingest_runs(id) ON DELETE CASCADE,
    document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
    source_path text NOT NULL,
    action text NOT NULL CHECK (action IN ('added', 'modified', 'removed', 'skipped', 'failed')),
    previous_sha256 text,
    new_sha256 text,
    error_message text,
    PRIMARY KEY (run_id, source_path)
);

CREATE TABLE IF NOT EXISTS document_pages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number integer NOT NULL,
    extracted_text text NOT NULL DEFAULT '',
    text_char_count integer NOT NULL DEFAULT 0,
    ocr_text text,
    ocr_quality_score numeric(6, 4),
    ocr_confidence numeric(6, 2),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, page_number)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id uuid REFERENCES document_pages(id) ON DELETE SET NULL,
    chunk_index integer NOT NULL,
    chunk_text text NOT NULL,
    token_count integer NOT NULL,
    section_title text,
    category text NOT NULL DEFAULT 'Uncategorized',
    quality_score numeric(6, 4) NOT NULL DEFAULT 0.0000,
    is_ocr boolean NOT NULL DEFAULT false,
    has_math boolean NOT NULL DEFAULT false,
    source_image_key text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS document_chunks_document_idx ON document_chunks (document_id, chunk_index);
CREATE INDEX IF NOT EXISTS document_chunks_page_idx ON document_chunks (page_id);
CREATE INDEX IF NOT EXISTS document_chunks_category_idx ON document_chunks (category);

CREATE TABLE IF NOT EXISTS chunk_quality_flags (
    chunk_id uuid NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    flag text NOT NULL,
    PRIMARY KEY (chunk_id, flag)
);

CREATE TABLE IF NOT EXISTS document_images (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id uuid REFERENCES document_pages(id) ON DELETE SET NULL,
    image_key text NOT NULL UNIQUE,
    image_ordinal integer NOT NULL,
    image_path text,
    width_px integer,
    height_px integer,
    caption text,
    ocr_text text,
    ocr_quality_score numeric(6, 4),
    ocr_confidence numeric(6, 2),
    sha256 text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, image_ordinal)
);

CREATE TABLE IF NOT EXISTS response_cache_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key text NOT NULL UNIQUE,
    index_fingerprint text NOT NULL,
    model_name text NOT NULL,
    retrieval_strategy text NOT NULL,
    question text NOT NULL,
    retrieval_query text NOT NULL,
    top_k integer NOT NULL,
    distance_threshold numeric(10, 6) NOT NULL,
    context_token_limit integer NOT NULL,
    show_full_text boolean NOT NULL,
    answer_markdown text NOT NULL,
    confidence_score numeric(6, 4),
    created_at timestamptz NOT NULL DEFAULT now(),
    last_accessed_at timestamptz NOT NULL DEFAULT now(),
    hit_count integer NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS response_cache_lookup_idx ON response_cache_entries (cache_key);

CREATE TABLE IF NOT EXISTS response_cache_sources (
    cache_entry_id uuid NOT NULL REFERENCES response_cache_entries(id) ON DELETE CASCADE,
    rank integer NOT NULL,
    document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
    chunk_id uuid REFERENCES document_chunks(id) ON DELETE SET NULL,
    source_path text NOT NULL,
    page_number integer,
    distance numeric(10, 6),
    preview text,
    PRIMARY KEY (cache_entry_id, rank)
);

CREATE TABLE IF NOT EXISTS query_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asked_at timestamptz NOT NULL DEFAULT now(),
    username citext REFERENCES users(username) ON DELETE SET NULL,
    model_name text NOT NULL,
    retrieval_strategy text NOT NULL,
    question text NOT NULL,
    retrieval_query text NOT NULL,
    elapsed_ms integer NOT NULL,
    cache_hit boolean NOT NULL DEFAULT false,
    confidence_score numeric(6, 4)
);

CREATE TABLE IF NOT EXISTS query_log_sources (
    query_log_id uuid NOT NULL REFERENCES query_logs(id) ON DELETE CASCADE,
    rank integer NOT NULL,
    document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
    chunk_id uuid REFERENCES document_chunks(id) ON DELETE SET NULL,
    source_path text NOT NULL,
    page_number integer,
    distance numeric(10, 6),
    PRIMARY KEY (query_log_id, rank)
);

INSERT INTO schema_migrations (version, name)
VALUES (1, 'initial_catalog')
ON CONFLICT (version) DO NOTHING;

COMMIT;
