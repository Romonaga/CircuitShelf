SELECT provider_project_id, provider_api_key_id
  FROM system_ai_provider_settings s
  JOIN ai_provider_types p ON p.id = s.provider_type_id
 WHERE p.code = 'openai'
UNION ALL
SELECT provider_project_id, provider_api_key_id
  FROM entity_ai_provider_settings s
  JOIN ai_provider_types p ON p.id = s.provider_type_id
 WHERE p.code = 'openai'
UNION ALL
SELECT provider_project_id, provider_api_key_id
  FROM user_ai_provider_settings s
  JOIN ai_provider_types p ON p.id = s.provider_type_id
 WHERE p.code = 'openai';
