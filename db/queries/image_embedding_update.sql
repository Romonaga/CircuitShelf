UPDATE document_images
SET embedding_model = %s,
    embedding = %s::vector
WHERE image_key = %s;
