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
       c.embedding_model,
       c.embedding::text AS embedding,
       p.page_number,
       array_remove(array_agg(q.flag ORDER BY q.flag), NULL) AS quality_flags
FROM document_chunks c
JOIN documents d ON d.id = c.document_id
LEFT JOIN document_pages p ON p.id = c.page_id
LEFT JOIN chunk_quality_flags q ON q.chunk_id = c.id
WHERE d.status_id = 3
GROUP BY d.source_path,
         c.chunk_index,
         c.chunk_text,
         c.token_count,
         c.section_title,
         c.category,
         c.quality_score,
         c.is_ocr,
         c.has_math,
         c.source_image_key,
         c.embedding_model,
         c.embedding,
         p.page_number
ORDER BY d.source_path, c.chunk_index;
