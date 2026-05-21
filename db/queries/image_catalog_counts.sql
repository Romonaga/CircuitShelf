SELECT
    (SELECT count(*) FROM document_images WHERE image_bytes IS NOT NULL) AS stored_images,
    (SELECT count(*) FROM document_images WHERE embedding IS NOT NULL) AS embeddings,
    (
        SELECT count(DISTINCT source_image_key)
        FROM document_chunks
        WHERE source_image_key IS NOT NULL
    ) AS referenced_images;
