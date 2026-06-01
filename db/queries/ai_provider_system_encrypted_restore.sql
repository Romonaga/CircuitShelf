INSERT INTO system_ai_provider_settings (
    provider_type_id,
    enabled,
    encrypted_api_key,
    key_preview,
    assist_mode_id,
    default_model,
    updated_by,
    updated_at
)
SELECT p.id, %s, %s, %s, am.id, %s, %s, now()
FROM ai_provider_types p
JOIN ai_assist_modes am ON am.code = %s
WHERE p.code = %s
ON CONFLICT (provider_type_id) DO UPDATE SET
    enabled = EXCLUDED.enabled,
    encrypted_api_key = EXCLUDED.encrypted_api_key,
    key_preview = EXCLUDED.key_preview,
    assist_mode_id = EXCLUDED.assist_mode_id,
    default_model = EXCLUDED.default_model,
    updated_by = EXCLUDED.updated_by,
    updated_at = now();
