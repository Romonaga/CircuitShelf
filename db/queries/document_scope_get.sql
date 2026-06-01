SELECT d.source_path,
       d.display_name,
       d.status,
       d.entity_id,
       e.name AS entity_name,
       d.is_global
FROM documents d
LEFT JOIN entities e ON e.id = d.entity_id
WHERE d.source_path = %s;
