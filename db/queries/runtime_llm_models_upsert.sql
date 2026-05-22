INSERT INTO llm_models (
    model_name,
    display_name,
    provider,
    is_default,
    is_enabled,
    temperature,
    num_predict,
    num_ctx,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
ON CONFLICT (model_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    provider = EXCLUDED.provider,
    is_default = EXCLUDED.is_default,
    is_enabled = EXCLUDED.is_enabled,
    temperature = EXCLUDED.temperature,
    num_predict = EXCLUDED.num_predict,
    num_ctx = EXCLUDED.num_ctx,
    updated_at = now();
