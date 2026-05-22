INSERT INTO rerank_profile_keywords (profile_id, keyword, weight)
VALUES (%s, %s, %s)
ON CONFLICT (profile_id, keyword) DO UPDATE SET
    weight = EXCLUDED.weight;
