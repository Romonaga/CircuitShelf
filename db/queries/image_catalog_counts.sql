SELECT
    (
        SELECT count(*)
        FROM document_images i
        JOIN documents d ON d.id = i.document_id
        WHERE d.status = 'indexed'
          AND i.image_bytes IS NOT NULL
    ) AS stored_images,
    (
        SELECT count(*)
        FROM document_images i
        JOIN documents d ON d.id = i.document_id
        WHERE d.status = 'indexed'
          AND i.embedding IS NOT NULL
    ) AS embeddings,
    (
        SELECT count(DISTINCT source_image_key)
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.status = 'indexed'
          AND c.source_image_key IS NOT NULL
    ) AS referenced_images;
