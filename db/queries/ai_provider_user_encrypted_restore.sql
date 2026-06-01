INSERT INTO user_ai_provider_settings (
    user_id,
    provider_type_id,
    enabled,
    encrypted_api_key,
    key_preview,
    key_policy_id,
    assist_mode_id,
    default_model,
    monthly_budget,
    warn_percent,
    stop_percent,
    updated_at
)
SELECT %s, p.id, %s, %s, %s, kp.id, am.id, %s, %s, %s, %s, now()
FROM ai_provider_types p
JOIN ai_key_policies kp ON kp.code = %s
JOIN ai_assist_modes am ON am.code = %s
WHERE p.code = %s
ON CONFLICT (user_id, provider_type_id) DO UPDATE SET
    enabled = EXCLUDED.enabled,
    encrypted_api_key = EXCLUDED.encrypted_api_key,
    key_preview = EXCLUDED.key_preview,
    key_policy_id = EXCLUDED.key_policy_id,
    assist_mode_id = EXCLUDED.assist_mode_id,
    default_model = EXCLUDED.default_model,
    monthly_budget = EXCLUDED.monthly_budget,
    warn_percent = EXCLUDED.warn_percent,
    stop_percent = EXCLUDED.stop_percent,
    updated_at = now();
