SELECT d.source_path,
       d.display_name,
       i.id,
       i.component_name,
       i.component_type,
       i.summary,
       i.confidence,
       i.updated_at
FROM document_intelligence i
JOIN documents d ON d.id = i.document_id
WHERE d.source_path = %s;
