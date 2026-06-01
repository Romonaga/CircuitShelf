SELECT
    rp.id,
    rp.name,
    rp.weight_vector,
    rp.weight_rerank,
    rp.is_default,
    rp.updated_at,
    COALESCE(
        array_agg(rpk.keyword ORDER BY rpk.keyword) FILTER (WHERE rpk.keyword IS NOT NULL),
        ARRAY[]::text[]
    ) AS keywords
FROM rerank_profiles rp
LEFT JOIN rerank_profile_keywords rpk ON rpk.profile_id = rp.id
GROUP BY rp.id
ORDER BY rp.is_default DESC, rp.name ASC;
