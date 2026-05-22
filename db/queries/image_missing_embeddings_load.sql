SELECT image_key,
       coalesce(ocr_text, caption, image_key) AS embedding_text
FROM document_images
WHERE embedding IS NULL
  AND coalesce(ocr_text, caption, image_key) <> ''
ORDER BY created_at NULLS LAST, image_key
LIMIT %s;
