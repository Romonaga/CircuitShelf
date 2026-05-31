SELECT p.code AS provider_code,
       s.enabled,
       CASE
           WHEN s.encrypted_api_key = '' THEN ''
           ELSE pgp_sym_decrypt(decode(s.encrypted_api_key, 'base64'), %s::text)
       END AS api_key,
       s.key_preview,
       kp.code AS key_policy,
       am.code AS assist_mode,
       s.default_model,
       s.monthly_budget,
       s.warn_percent,
       s.stop_percent
FROM entity_ai_provider_settings s
JOIN ai_provider_types p ON p.id = s.provider_type_id
JOIN ai_key_policies kp ON kp.id = s.key_policy_id
JOIN ai_assist_modes am ON am.id = s.assist_mode_id
WHERE s.entity_id = %s
  AND p.code = %s;
