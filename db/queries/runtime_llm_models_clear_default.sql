UPDATE llm_models
SET is_default = false,
    updated_at = now()
WHERE is_default = true;
