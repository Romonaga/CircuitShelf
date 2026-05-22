INSERT INTO document_intelligence (
    document_id,
    component_name,
    component_type,
    summary,
    confidence,
    updated_at
)
SELECT id, %s, %s, %s, %s, now()
FROM documents
WHERE source_path = %s
ON CONFLICT (document_id) DO UPDATE SET
    component_name = EXCLUDED.component_name,
    component_type = EXCLUDED.component_type,
    summary = EXCLUDED.summary,
    confidence = EXCLUDED.confidence,
    updated_at = now()
RETURNING id;
