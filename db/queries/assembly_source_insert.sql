INSERT INTO assembly_plan_sources (
    plan_id,
    source_path,
    display_name,
    pages,
    chunk_count
)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (plan_id, source_path) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    pages = EXCLUDED.pages,
    chunk_count = EXCLUDED.chunk_count;
