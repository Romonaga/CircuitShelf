INSERT INTO equation_patterns (pattern_type, pattern, is_regex)
VALUES (%s, %s, %s)
ON CONFLICT (pattern_type, pattern) DO UPDATE SET
    is_regex = EXCLUDED.is_regex;
