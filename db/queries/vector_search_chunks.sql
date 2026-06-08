SELECT d.source_path,
       c.chunk_index,
       c.chunk_text,
       c.token_count,
       c.section_title,
       c.category,
       c.quality_score,
       c.is_ocr,
       c.has_math,
       c.source_image_key,
       p.page_number,
       c.embedding <-> %s::vector AS distance
FROM document_chunks c
JOIN documents d ON d.id = c.document_id
LEFT JOIN document_pages p ON p.id = c.page_id
WHERE d.status_id = 3
  AND document_visible_to_entity(d.is_global, d.entity_id, %s::bigint)
  AND c.embedding IS NOT NULL
ORDER BY c.embedding <-> %s::vector
LIMIT %s;
