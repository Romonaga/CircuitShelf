SELECT key,
       value_type,
       text_value,
       integer_value,
       numeric_value,
       boolean_value
FROM app_settings
ORDER BY key;
