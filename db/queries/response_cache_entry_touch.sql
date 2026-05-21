UPDATE response_cache_entries
SET last_accessed_at = now(),
    hit_count = hit_count + 1
WHERE id = %s;
