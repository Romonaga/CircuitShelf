INSERT INTO documents (
    source_path,
    display_name,
    file_extension,
    size_bytes,
    mtime_ns,
    sha256,
    status,
    raw_chunk_count,
    chunk_count,
    dropped_chunk_count,
    extracted_image_count,
    indexed_image_text_count,
    ocr_image_text_count,
    last_ingested_at,
    last_error
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), NULL)
ON CONFLICT (source_path) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    file_extension = EXCLUDED.file_extension,
    size_bytes = EXCLUDED.size_bytes,
    mtime_ns = EXCLUDED.mtime_ns,
    sha256 = EXCLUDED.sha256,
    status = EXCLUDED.status,
    raw_chunk_count = EXCLUDED.raw_chunk_count,
    chunk_count = EXCLUDED.chunk_count,
    dropped_chunk_count = EXCLUDED.dropped_chunk_count,
    extracted_image_count = EXCLUDED.extracted_image_count,
    indexed_image_text_count = EXCLUDED.indexed_image_text_count,
    ocr_image_text_count = EXCLUDED.ocr_image_text_count,
    last_ingested_at = now(),
    last_error = NULL,
    updated_at = now()
RETURNING id;
