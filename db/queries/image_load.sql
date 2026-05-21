SELECT image_key,
       encode(image_bytes, 'base64') AS image_base64,
       caption,
       ocr_text
FROM document_images
WHERE image_bytes IS NOT NULL
ORDER BY image_key;
