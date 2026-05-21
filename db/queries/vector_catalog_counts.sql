SELECT
    (SELECT count(*) FROM documents WHERE status = 'indexed') AS documents,
    (SELECT count(*) FROM document_chunks WHERE embedding IS NOT NULL) AS chunks,
    (SELECT count(*) FROM document_chunks WHERE embedding IS NOT NULL) AS embeddings;
