SELECT
    (
        SELECT count(*)
        FROM documents
        WHERE status = 'indexed'
          AND document_visible_to_entity(is_global, entity_id, %s::bigint)
    ) AS documents,
    (
        SELECT count(*)
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.status = 'indexed'
          AND document_visible_to_entity(d.is_global, d.entity_id, %s::bigint)
          AND c.embedding IS NOT NULL
    ) AS chunks,
    (
        SELECT count(*)
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.status = 'indexed'
          AND document_visible_to_entity(d.is_global, d.entity_id, %s::bigint)
          AND c.embedding IS NOT NULL
    ) AS embeddings;
