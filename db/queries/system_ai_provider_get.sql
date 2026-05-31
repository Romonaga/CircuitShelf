SELECT p.code AS provider_code,
       s.enabled,
       s.key_preview,
       am.code AS assist_mode,
       s.default_model,
       s.updated_at
FROM system_ai_provider_settings s
JOIN ai_provider_types p ON p.id = s.provider_type_id
JOIN ai_assist_modes am ON am.id = s.assist_mode_id
WHERE p.code = %s;
