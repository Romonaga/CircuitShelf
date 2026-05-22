WITH image_stats AS (
    SELECT document_id,
           count(*) AS stored_image_count,
           count(*) FILTER (WHERE coalesce(ocr_text, '') <> '') AS ocr_image_text_count,
           count(*) FILTER (WHERE embedding IS NOT NULL) AS indexed_image_text_count
    FROM document_images
    GROUP BY document_id
)
UPDATE documents d
SET stored_image_count = coalesce(i.stored_image_count, 0),
    ocr_image_text_count = coalesce(i.ocr_image_text_count, 0),
    indexed_image_text_count = coalesce(i.indexed_image_text_count, 0),
    extracted_image_count = GREATEST(d.extracted_image_count, coalesce(i.stored_image_count, 0)),
    updated_at = now()
FROM documents target
LEFT JOIN image_stats i ON i.document_id = target.id
WHERE d.id = target.id
  AND (%s::text[] IS NULL OR d.source_path = ANY(%s::text[]));
