INSERT INTO document_chunks (
    document_id,
    page_id,
    chunk_index,
    chunk_text,
    token_count,
    section_title,
    category,
    quality_score,
    is_ocr,
    has_math,
    source_image_key,
    embedding_model,
    embedding
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
RETURNING id;
