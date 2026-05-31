SELECT p.code AS provider_code,
       amp.model_name,
       amp.input_per_million,
       amp.cached_input_per_million,
       amp.output_per_million,
       amp.currency,
       amp.is_active,
       amp.updated_at
FROM ai_model_pricing amp
JOIN ai_provider_types p ON p.id = amp.provider_type_id
WHERE p.code = %s
ORDER BY amp.is_active DESC, amp.model_name;
