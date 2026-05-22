SELECT image_key,
       caption,
       ocr_text,
       image_mime_type,
       encode(image_bytes, 'base64') AS image_base64,
       embedding <-> %s::vector AS distance
FROM document_images
WHERE embedding IS NOT NULL
  AND image_bytes IS NOT NULL
ORDER BY embedding <-> %s::vector
LIMIT %s;
