SELECT p.code AS provider_code,
       o.model_name,
       bst.code AS scope,
       o.entity_id,
       o.user_id,
       o.input_per_million,
       o.cached_input_per_million,
       o.output_per_million,
       o.currency,
       o.updated_at
FROM ai_model_pricing_overrides o
JOIN ai_provider_types p ON p.id = o.provider_type_id
JOIN ai_billing_scope_types bst ON bst.id = o.billing_scope_type_id
WHERE p.code = %s
  AND bst.code = %s
  AND (%s::bigint IS NULL OR o.entity_id = %s::bigint)
  AND (%s::bigint IS NULL OR o.user_id = %s::bigint)
ORDER BY o.model_name;
