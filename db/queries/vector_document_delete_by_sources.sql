DELETE FROM documents
WHERE source_path = ANY(%s);
