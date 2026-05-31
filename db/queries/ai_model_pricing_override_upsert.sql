INSERT INTO ai_model_pricing_overrides (
    provider_type_id,
    model_name,
    billing_scope_type_id,
    entity_id,
    user_id,
    input_per_million,
    cached_input_per_million,
    output_per_million,
    currency,
    updated_by,
    updated_at
)
VALUES (
    (SELECT id FROM ai_provider_types WHERE code = %s),
    %s,
    (SELECT id FROM ai_billing_scope_types WHERE code = %s),
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    now()
)
ON CONFLICT (provider_type_id, model_name, billing_scope_type_id, entity_id, user_id)
DO UPDATE SET
    input_per_million = EXCLUDED.input_per_million,
    cached_input_per_million = EXCLUDED.cached_input_per_million,
    output_per_million = EXCLUDED.output_per_million,
    currency = EXCLUDED.currency,
    updated_by = EXCLUDED.updated_by,
    updated_at = now()
RETURNING id;
