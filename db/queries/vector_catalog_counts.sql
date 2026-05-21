SELECT
    (SELECT count(*) FROM documents WHERE status = 'indexed') AS documents,
    (
        SELECT count(*)
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.status = 'indexed'
          AND c.embedding IS NOT NULL
    ) AS chunks,
    (
        SELECT count(*)
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.status = 'indexed'
          AND c.embedding IS NOT NULL
    ) AS embeddings;
