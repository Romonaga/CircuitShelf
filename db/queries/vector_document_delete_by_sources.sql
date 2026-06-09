WITH deleted_documents AS (
    DELETE FROM documents
    WHERE source_path = ANY(%s)
    RETURNING source_path
),
deleted_ingest_scopes AS (
    DELETE FROM document_ingest_scope_overrides
    WHERE source_path IN (SELECT source_path FROM deleted_documents)
    RETURNING source_path
)
SELECT count(*) AS deleted_documents,
       (SELECT count(*) FROM deleted_ingest_scopes) AS deleted_ingest_scopes
FROM deleted_documents;
