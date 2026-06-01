SELECT p.code AS provider_code,
       v.model_name,
       v.context_band,
       v.service_tier,
       v.input_per_million,
       v.cached_input_per_million,
       v.output_per_million,
       v.currency,
       v.source_note,
       v.is_active,
       v.updated_at
FROM ai_model_pricing_variants v
JOIN ai_provider_types p ON p.id = v.provider_type_id
WHERE p.code = %s
ORDER BY v.model_name, v.service_tier, v.context_band;
