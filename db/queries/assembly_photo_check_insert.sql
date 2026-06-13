INSERT INTO assembly_photo_checks (
    plan_id,
    step_id,
    user_id,
    image_mime_type,
    image_base64,
    note,
    checklist,
    diagnostics,
    verification_status,
    verification_confidence,
    verification_summary,
    verification_findings,
    requested_evidence,
    verification_provider,
    verification_model,
    ai_result
)
SELECT ap.id, aps.id, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb
FROM assembly_plans ap
LEFT JOIN assembly_plan_steps aps
  ON aps.plan_id = ap.id
 AND aps.id = %s
WHERE ap.id = %s
  AND ap.user_id = %s
  AND (%s::uuid IS NULL OR aps.id IS NOT NULL)
RETURNING id,
          plan_id,
          step_id,
          user_id,
          image_mime_type,
          note,
          checklist,
          diagnostics,
          verification_status,
          verification_confidence,
          verification_summary,
          verification_findings,
          requested_evidence,
          verification_provider,
          verification_model,
          ai_result,
          created_at;
