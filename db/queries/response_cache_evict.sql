DELETE FROM response_cache_entries
WHERE id IN (
    SELECT id
    FROM response_cache_entries
    ORDER BY last_accessed_at DESC
    OFFSET %s
);
