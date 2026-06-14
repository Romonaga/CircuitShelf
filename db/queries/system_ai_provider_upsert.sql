INSERT INTO system_ai_provider_settings (
    provider_type_id,
    enabled,
    encrypted_api_key,
    key_preview,
    provider_project_id,
    provider_api_key_id,
    assist_mode_id,
    default_model,
    updated_by,
    updated_at
)
VALUES (
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
    now()
)
ON CONFLICT (provider_type_id) DO UPDATE SET
    enabled = EXCLUDED.enabled,
    encrypted_api_key = CASE
        WHEN %s::boolean THEN EXCLUDED.encrypted_api_key
        ELSE system_ai_provider_settings.encrypted_api_key
    END,
    key_preview = CASE
        WHEN %s::boolean THEN EXCLUDED.key_preview
        ELSE system_ai_provider_settings.key_preview
    END,
    provider_project_id = EXCLUDED.provider_project_id,
    provider_api_key_id = EXCLUDED.provider_api_key_id,
    assist_mode_id = EXCLUDED.assist_mode_id,
    default_model = EXCLUDED.default_model,
    updated_by = EXCLUDED.updated_by,
    updated_at = now()
RETURNING provider_type_id;
