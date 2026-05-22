INSERT INTO chunk_category_keywords (category_id, keyword)
VALUES (%s, %s)
ON CONFLICT (category_id, keyword) DO NOTHING;
