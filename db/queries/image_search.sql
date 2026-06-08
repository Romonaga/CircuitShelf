SELECT image_key,
       caption,
       ocr_text,
       image_mime_type,
       encode(image_bytes, 'base64') AS image_base64,
       embedding <-> %s::vector AS distance
FROM document_images i
JOIN documents d ON d.id = i.document_id
WHERE i.embedding IS NOT NULL
  AND i.image_bytes IS NOT NULL
  AND d.status_id = 3
  AND document_visible_to_entity(d.is_global, d.entity_id, %s::bigint)
ORDER BY embedding <-> %s::vector
LIMIT %s;
