SELECT
    id,
    model_name,
    display_name,
    provider,
    is_default,
    is_enabled,
    temperature,
    num_predict,
    num_ctx,
    updated_at
FROM llm_models
ORDER BY provider ASC, is_default DESC, display_name ASC, model_name ASC;
