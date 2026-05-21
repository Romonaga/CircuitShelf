INSERT INTO document_images (
    document_id,
    page_id,
    image_key,
    image_ordinal,
    image_bytes,
    image_mime_type,
    width_px,
    height_px,
    caption,
    ocr_text,
    ocr_quality_score,
    ocr_confidence,
    sha256,
    embedding_model,
    embedding
)
VALUES (
    %s,
    (
        SELECT id
        FROM document_pages
        WHERE document_id = %s
          AND page_number = %s
        LIMIT 1
    ),
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s::vector
)
ON CONFLICT (image_key) DO UPDATE SET
    document_id = EXCLUDED.document_id,
    page_id = EXCLUDED.page_id,
    image_ordinal = EXCLUDED.image_ordinal,
    image_bytes = EXCLUDED.image_bytes,
    image_mime_type = EXCLUDED.image_mime_type,
    width_px = EXCLUDED.width_px,
    height_px = EXCLUDED.height_px,
    caption = EXCLUDED.caption,
    ocr_text = EXCLUDED.ocr_text,
    ocr_quality_score = EXCLUDED.ocr_quality_score,
    ocr_confidence = EXCLUDED.ocr_confidence,
    sha256 = EXCLUDED.sha256,
    embedding_model = EXCLUDED.embedding_model,
    embedding = EXCLUDED.embedding;
