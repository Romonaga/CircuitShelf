SELECT
    id,
    pattern_type,
    pattern,
    is_regex,
    created_at
FROM equation_patterns
ORDER BY pattern_type ASC, pattern ASC;
