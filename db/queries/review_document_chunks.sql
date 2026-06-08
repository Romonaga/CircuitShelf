SELECT d.source_path,
       d.display_name,
       ds.code AS status,
       d.status_id,
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
       array_remove(array_agg(q.flag ORDER BY q.flag), NULL) AS quality_flags
FROM documents d
JOIN document_statuses ds ON ds.id = d.status_id
JOIN document_chunks c ON c.document_id = d.id
LEFT JOIN document_pages p ON p.id = c.page_id
LEFT JOIN chunk_quality_flags q ON q.chunk_id = c.id
WHERE d.source_path = %s
GROUP BY d.source_path,
         d.display_name,
         ds.code,
         d.status_id,
         c.chunk_index,
         c.chunk_text,
         c.token_count,
         c.section_title,
         c.category,
         c.quality_score,
         c.is_ocr,
         c.has_math,
         c.source_image_key,
         p.page_number
ORDER BY c.chunk_index
LIMIT %s;
