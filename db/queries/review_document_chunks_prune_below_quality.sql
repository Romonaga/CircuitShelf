WITH target_document AS (
    SELECT id
    FROM documents
    WHERE source_path = %s
),
deleted_chunks AS (
    DELETE FROM document_chunks c
    USING target_document d
    WHERE c.document_id = d.id
      AND c.quality_score < %s
    RETURNING c.source_image_key
)
SELECT count(*) AS pruned_chunks,
       count(*) FILTER (WHERE source_image_key IS NOT NULL) AS pruned_image_chunks
FROM deleted_chunks;
