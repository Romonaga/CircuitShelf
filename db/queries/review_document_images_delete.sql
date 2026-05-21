UPDATE document_chunks
SET source_image_key = NULL
WHERE document_id = (
    SELECT id
    FROM documents
    WHERE source_path = %s
);

DELETE FROM document_images
WHERE document_id = (
    SELECT id
    FROM documents
    WHERE source_path = %s
);
