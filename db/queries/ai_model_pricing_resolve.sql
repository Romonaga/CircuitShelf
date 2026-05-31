SELECT p.provider_code,
       p.model_name,
       coalesce(o.input_per_million, p.input_per_million) AS input_per_million,
       coalesce(o.cached_input_per_million, p.cached_input_per_million) AS cached_input_per_million,
       coalesce(o.output_per_million, p.output_per_million) AS output_per_million,
       coalesce(o.currency, p.currency) AS currency,
       (o.id IS NOT NULL) AS is_override
FROM (
    SELECT apt.id AS provider_type_id,
           apt.code AS provider_code,
           amp.model_name,
           amp.input_per_million,
           amp.cached_input_per_million,
           amp.output_per_million,
           amp.currency
    FROM ai_model_pricing amp
    JOIN ai_provider_types apt ON apt.id = amp.provider_type_id
    WHERE apt.code = %s
      AND amp.model_name = %s
      AND amp.is_active = true
) p
LEFT JOIN ai_billing_scope_types bst ON bst.code = %s
LEFT JOIN ai_model_pricing_overrides o
       ON o.provider_type_id = p.provider_type_id
      AND o.model_name = p.model_name
      AND o.billing_scope_type_id = bst.id
      AND (
          (%s = 'system' AND o.entity_id IS NULL AND o.user_id IS NULL)
          OR (%s = 'entity' AND o.entity_id = %s::bigint AND o.user_id IS NULL)
          OR (%s = 'user' AND o.entity_id IS NULL AND o.user_id = %s::bigint)
      );
