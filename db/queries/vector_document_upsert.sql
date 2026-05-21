INSERT INTO documents (
    source_path,
    display_name,
    file_extension,
    size_bytes,
    mtime_ns,
    sha256,
    status,
    last_ingested_at,
    last_error
)
VALUES (%s, %s, %s, %s, %s, %s, 'indexed', now(), NULL)
ON CONFLICT (source_path) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    file_extension = EXCLUDED.file_extension,
    size_bytes = EXCLUDED.size_bytes,
    mtime_ns = EXCLUDED.mtime_ns,
    sha256 = EXCLUDED.sha256,
    status = 'indexed',
    last_ingested_at = now(),
    last_error = NULL,
    updated_at = now()
RETURNING id;
