WITH target_document AS (
    SELECT id
    FROM documents
    WHERE source_path = %s
),
cleared_chunks AS (
    UPDATE document_chunks
    SET source_image_key = NULL
    WHERE document_id = (SELECT id FROM target_document)
    RETURNING 1
)
DELETE FROM document_images
WHERE document_id = (SELECT id FROM target_document);
