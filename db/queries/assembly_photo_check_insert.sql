INSERT INTO assembly_photo_checks (
    plan_id,
    user_id,
    image_mime_type,
    image_base64,
    note,
    checklist,
    diagnostics
)
SELECT id, %s, %s, %s, %s, %s, %s::jsonb
FROM assembly_plans
WHERE id = %s
  AND user_id = %s
RETURNING id, plan_id, user_id, image_mime_type, note, checklist, diagnostics, created_at;
