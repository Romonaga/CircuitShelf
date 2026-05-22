SELECT
    cc.name,
    cc.detail_level,
    cc.priority,
    COALESCE(
        array_agg(cck.keyword ORDER BY cck.keyword) FILTER (WHERE cck.keyword IS NOT NULL),
        ARRAY[]::text[]
    ) AS keywords
FROM chunk_categories cc
LEFT JOIN chunk_category_keywords cck ON cck.category_id = cc.id
GROUP BY cc.id
ORDER BY cc.priority DESC, cc.name ASC;
