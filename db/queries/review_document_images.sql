SELECT d.source_path,
       d.display_name,
       d.status,
       i.image_key,
       i.caption,
       i.width_px,
       i.height_px,
       i.image_mime_type,
       p.page_number,
       encode(i.image_bytes, 'base64') AS image_base64
FROM documents d
JOIN document_images i ON i.document_id = d.id
LEFT JOIN document_pages p ON p.id = i.page_id
WHERE d.source_path = %s
ORDER BY p.page_number NULLS LAST, i.image_ordinal, i.image_key;
