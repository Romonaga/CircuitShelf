SELECT id, source_path, display_name, pages, chunk_count
FROM assembly_plan_sources
WHERE plan_id = %s
ORDER BY display_name ASC, source_path ASC;
