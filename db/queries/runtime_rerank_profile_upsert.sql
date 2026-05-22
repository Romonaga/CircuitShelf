INSERT INTO rerank_profiles (
    name,
    weight_vector,
    weight_rerank,
    is_default,
    updated_at
)
VALUES (%s, %s, %s, %s, now())
ON CONFLICT (name) DO UPDATE SET
    weight_vector = EXCLUDED.weight_vector,
    weight_rerank = EXCLUDED.weight_rerank,
    is_default = EXCLUDED.is_default,
    updated_at = now()
RETURNING id;
