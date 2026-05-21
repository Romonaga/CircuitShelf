SELECT d.source_path,
       d.display_name,
       d.file_extension,
       d.size_bytes,
       d.mtime_ns,
       d.status,
       d.last_ingested_at,
       d.last_error,
       d.created_at,
       d.updated_at,
       count(DISTINCT c.id) AS chunk_count,
       count(DISTINCT i.id) AS image_count,
       coalesce(avg(c.quality_score), 0) AS avg_quality,
       count(DISTINCT c.id) FILTER (WHERE c.quality_score < 0.35) AS low_quality_count
FROM documents d
LEFT JOIN document_chunks c ON c.document_id = d.id
LEFT JOIN document_images i ON i.document_id = d.id
WHERE d.status IN ('needs_review', 'failed')
GROUP BY d.id
ORDER BY d.updated_at DESC, d.source_path;
