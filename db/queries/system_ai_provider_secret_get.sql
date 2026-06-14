SELECT p.code AS provider_code,
       s.enabled,
       CASE
           WHEN s.encrypted_api_key = '' THEN ''
           ELSE pgp_sym_decrypt(decode(s.encrypted_api_key, 'base64'), %s::text)
       END AS api_key,
       CASE
           WHEN s.encrypted_admin_api_key = '' THEN ''
           ELSE pgp_sym_decrypt(decode(s.encrypted_admin_api_key, 'base64'), %s::text)
       END AS admin_api_key,
       s.key_preview,
       s.admin_key_preview,
       s.provider_project_id,
       s.provider_api_key_id,
       am.code AS assist_mode,
       s.default_model
FROM system_ai_provider_settings s
JOIN ai_provider_types p ON p.id = s.provider_type_id
JOIN ai_assist_modes am ON am.id = s.assist_mode_id
WHERE p.code = %s;
