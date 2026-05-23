SELECT i.image_key,
       i.caption,
       i.width_px,
       i.height_px,
       i.image_mime_type,
       encode(i.image_bytes, 'base64') AS image_base64,
       dp.page_number,
       d.source_path,
       d.display_name
FROM assembly_plan_steps aps
JOIN assembly_plans ap ON ap.id = aps.plan_id
JOIN documents d ON d.source_path = aps.source_path
JOIN document_images i ON i.document_id = d.id
LEFT JOIN document_pages dp ON dp.id = i.page_id
WHERE aps.id = %s
  AND aps.plan_id = %s
  AND i.image_bytes IS NOT NULL
  AND (%s::bigint IS NULL OR ap.user_id = %s)
  AND (
      aps.page_number IS NULL
      OR dp.page_number = aps.page_number
  )
ORDER BY dp.page_number NULLS LAST, i.image_ordinal, i.image_key
LIMIT %s;
