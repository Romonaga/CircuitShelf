SELECT rank,
       source_path,
       page_number,
       distance,
       preview,
       chunk_index,
       section_title,
       category,
       source_image_key
FROM response_cache_sources
WHERE cache_entry_id = %s
ORDER BY rank;
