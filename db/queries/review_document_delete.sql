WITH deleted_document AS (
    DELETE FROM documents
    WHERE source_path = %s
    RETURNING source_path, display_name
),
deleted_ingest_scope AS (
    DELETE FROM document_ingest_scope_overrides
    WHERE source_path IN (SELECT source_path FROM deleted_document)
    RETURNING source_path
)
SELECT source_path,
       display_name,
       (SELECT count(*) FROM deleted_ingest_scope) AS deleted_ingest_scope_count
FROM deleted_document;
