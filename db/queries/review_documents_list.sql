WITH chunk_stats AS (
    SELECT document_id,
           count(*) AS chunk_count,
           coalesce(avg(quality_score), 0) AS avg_quality,
           count(*) FILTER (WHERE quality_score < 0.35) AS low_quality_count
    FROM document_chunks
    GROUP BY document_id
),
image_stats AS (
    SELECT document_id,
           count(*) AS image_count
    FROM document_images
    GROUP BY document_id
)
SELECT d.source_path,
       d.display_name,
       d.file_extension,
       d.size_bytes,
       d.mtime_ns,
       d.status,
       d.raw_chunk_count,
       d.dropped_chunk_count,
       d.extracted_image_count,
       d.stored_image_count,
       d.indexed_image_text_count,
       d.ocr_image_text_count,
       d.last_ingested_at,
       d.last_error,
       d.created_at,
       d.updated_at,
       coalesce(c.chunk_count, 0) AS chunk_count,
       coalesce(i.image_count, 0) AS image_count,
       coalesce(c.avg_quality, 0) AS avg_quality,
       coalesce(c.low_quality_count, 0) AS low_quality_count
FROM documents d
LEFT JOIN chunk_stats c ON c.document_id = d.id
LEFT JOIN image_stats i ON i.document_id = d.id
WHERE d.status IN ('needs_review', 'failed')
ORDER BY d.updated_at DESC, d.source_path;
