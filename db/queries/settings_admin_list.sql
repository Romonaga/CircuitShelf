SELECT key,
       value_type,
       text_value,
       integer_value,
       numeric_value,
       boolean_value,
       description,
       is_sensitive,
       updated_at
FROM app_settings
WHERE is_sensitive = false
ORDER BY key;
