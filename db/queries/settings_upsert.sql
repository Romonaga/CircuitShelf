INSERT INTO app_settings (
    key,
    value_type,
    text_value,
    integer_value,
    numeric_value,
    boolean_value,
    description,
    is_sensitive,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
ON CONFLICT (key) DO UPDATE SET
    value_type = EXCLUDED.value_type,
    text_value = EXCLUDED.text_value,
    integer_value = EXCLUDED.integer_value,
    numeric_value = EXCLUDED.numeric_value,
    boolean_value = EXCLUDED.boolean_value,
    description = EXCLUDED.description,
    is_sensitive = EXCLUDED.is_sensitive,
    updated_at = now();
