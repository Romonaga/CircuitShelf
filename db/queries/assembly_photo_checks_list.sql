SELECT id,
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
       created_at
FROM assembly_photo_checks
WHERE plan_id = %s
  AND user_id = %s
  AND (%s::uuid IS NULL OR step_id = %s)
ORDER BY created_at DESC
LIMIT %s;
