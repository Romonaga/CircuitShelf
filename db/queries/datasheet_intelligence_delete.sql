DELETE FROM document_intelligence
WHERE document_id = (
    SELECT id
    FROM documents
    WHERE source_path = %s
);
