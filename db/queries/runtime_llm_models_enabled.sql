SELECT
    model_name,
    display_name,
    provider,
    is_default,
    temperature,
    num_predict,
    num_ctx
FROM llm_models
WHERE is_enabled = true
ORDER BY is_default DESC, display_name ASC, model_name ASC;
