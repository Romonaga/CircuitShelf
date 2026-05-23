SELECT id,
       plan_id,
       user_id,
       image_mime_type,
       note,
       checklist,
       created_at
FROM assembly_photo_checks
WHERE plan_id = %s
  AND user_id = %s
ORDER BY created_at DESC
LIMIT %s;
