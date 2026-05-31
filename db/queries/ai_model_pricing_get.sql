SELECT p.code AS provider_code,
       amp.model_name,
       amp.input_per_million,
       amp.cached_input_per_million,
       amp.output_per_million,
       amp.currency
FROM ai_model_pricing amp
JOIN ai_provider_types p ON p.id = amp.provider_type_id
WHERE p.code = %s
  AND amp.model_name = %s
  AND amp.is_active = true;
