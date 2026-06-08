SELECT d.source_path,
       d.display_name,
       ds.code AS status,
       d.status_id,
       d.entity_id,
       e.name AS entity_name,
       d.is_global
FROM documents d
JOIN document_statuses ds ON ds.id = d.status_id
LEFT JOIN entities e ON e.id = d.entity_id
WHERE d.source_path = %s;
