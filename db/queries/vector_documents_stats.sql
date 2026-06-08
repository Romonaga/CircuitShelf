WITH chunk_stats AS (
    SELECT document_id,
           count(*) AS actual_chunk_count
    FROM document_chunks
    GROUP BY document_id
),
image_stats AS (
    SELECT document_id,
           count(*) AS actual_image_count
    FROM document_images
    GROUP BY document_id
)
SELECT d.source_path,
       d.display_name,
       d.raw_chunk_count,
       d.chunk_count,
       d.dropped_chunk_count,
       d.extracted_image_count,
       d.stored_image_count,
       d.indexed_image_text_count,
       d.ocr_image_text_count,
       coalesce(c.actual_chunk_count, 0) AS actual_chunk_count,
       coalesce(i.actual_image_count, 0) AS actual_image_count
FROM documents d
LEFT JOIN chunk_stats c ON c.document_id = d.id
LEFT JOIN image_stats i ON i.document_id = d.id
WHERE d.status_id = 3
  AND (
      %s = 'global' AND d.is_global = true
      OR %s = 'visible' AND document_visible_to_entity(d.is_global, d.entity_id, %s::bigint)
  )
ORDER BY d.display_name;
