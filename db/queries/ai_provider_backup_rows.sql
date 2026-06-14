SELECT 'system' AS scope,
       NULL::bigint AS scope_id,
       p.code AS provider,
       s.enabled,
       s.encrypted_api_key,
       s.encrypted_admin_api_key,
       s.key_preview,
       s.admin_key_preview,
       s.provider_project_id,
       s.provider_api_key_id,
       'system' AS key_policy,
       am.code AS assist_mode,
       s.default_model,
       NULL::numeric AS monthly_budget,
       NULL::integer AS warn_percent,
       NULL::integer AS stop_percent,
       s.updated_by,
       s.updated_at
FROM system_ai_provider_settings s
JOIN ai_provider_types p ON p.id = s.provider_type_id
JOIN ai_assist_modes am ON am.id = s.assist_mode_id
UNION ALL
SELECT 'entity' AS scope,
       s.entity_id AS scope_id,
       p.code AS provider,
       s.enabled,
       s.encrypted_api_key,
       NULL::text AS encrypted_admin_api_key,
       s.key_preview,
       NULL::text AS admin_key_preview,
       s.provider_project_id,
       s.provider_api_key_id,
       kp.code AS key_policy,
       am.code AS assist_mode,
       s.default_model,
       s.monthly_budget,
       s.warn_percent,
       s.stop_percent,
       s.updated_by,
       s.updated_at
FROM entity_ai_provider_settings s
JOIN ai_provider_types p ON p.id = s.provider_type_id
JOIN ai_key_policies kp ON kp.id = s.key_policy_id
JOIN ai_assist_modes am ON am.id = s.assist_mode_id
UNION ALL
SELECT 'user' AS scope,
       s.user_id AS scope_id,
       p.code AS provider,
       s.enabled,
       s.encrypted_api_key,
       NULL::text AS encrypted_admin_api_key,
       s.key_preview,
       NULL::text AS admin_key_preview,
       s.provider_project_id,
       s.provider_api_key_id,
       kp.code AS key_policy,
       am.code AS assist_mode,
       s.default_model,
       s.monthly_budget,
       s.warn_percent,
       s.stop_percent,
       NULL::bigint AS updated_by,
       s.updated_at
FROM user_ai_provider_settings s
JOIN ai_provider_types p ON p.id = s.provider_type_id
JOIN ai_key_policies kp ON kp.id = s.key_policy_id
JOIN ai_assist_modes am ON am.id = s.assist_mode_id
ORDER BY scope, scope_id NULLS FIRST, provider;
