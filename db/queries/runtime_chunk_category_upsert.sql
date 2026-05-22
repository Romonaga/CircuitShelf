INSERT INTO chunk_categories (
    name,
    detail_level,
    priority
)
VALUES (%s, %s, %s)
ON CONFLICT (name) DO UPDATE SET
    detail_level = EXCLUDED.detail_level,
    priority = EXCLUDED.priority
RETURNING id;
