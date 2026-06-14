INSERT INTO user_ai_provider_settings (
    user_id,
    provider_type_id,
    enabled,
    encrypted_api_key,
    key_preview,
    provider_project_id,
    provider_api_key_id,
    key_policy_id,
    assist_mode_id,
    default_model,
    monthly_budget,
    warn_percent,
    stop_percent,
    updated_at
)
VALUES (
    %s,
    %s,
    %s,
    CASE
        WHEN %s::text IS NULL THEN ''
        WHEN %s::text = '' THEN ''
        ELSE encode(pgp_sym_encrypt(%s::text, %s::text), 'base64')
    END,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    now()
)
ON CONFLICT (user_id, provider_type_id) DO UPDATE SET
    enabled = EXCLUDED.enabled,
    encrypted_api_key = CASE
        WHEN %s::boolean THEN EXCLUDED.encrypted_api_key
        ELSE user_ai_provider_settings.encrypted_api_key
    END,
    key_preview = CASE
        WHEN %s::boolean THEN EXCLUDED.key_preview
        ELSE user_ai_provider_settings.key_preview
    END,
    provider_project_id = EXCLUDED.provider_project_id,
    provider_api_key_id = EXCLUDED.provider_api_key_id,
    key_policy_id = EXCLUDED.key_policy_id,
    assist_mode_id = EXCLUDED.assist_mode_id,
    default_model = EXCLUDED.default_model,
    monthly_budget = EXCLUDED.monthly_budget,
    warn_percent = EXCLUDED.warn_percent,
    stop_percent = EXCLUDED.stop_percent,
    updated_at = now()
RETURNING user_id, provider_type_id;
