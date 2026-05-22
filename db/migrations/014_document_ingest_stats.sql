ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS raw_chunk_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS chunk_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS dropped_chunk_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS extracted_image_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS stored_image_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS indexed_image_text_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ocr_image_text_count integer NOT NULL DEFAULT 0;

WITH chunk_stats AS (
    SELECT document_id,
           count(*) AS chunk_count
    FROM document_chunks
    GROUP BY document_id
),
image_stats AS (
    SELECT document_id,
           count(*) AS stored_image_count,
           count(*) FILTER (WHERE coalesce(ocr_text, '') <> '') AS ocr_image_text_count,
           count(*) FILTER (WHERE embedding IS NOT NULL) AS indexed_image_text_count
    FROM document_images
    GROUP BY document_id
)
UPDATE documents d
SET chunk_count = coalesce(c.chunk_count, 0),
    raw_chunk_count = GREATEST(d.raw_chunk_count, coalesce(c.chunk_count, 0)),
    stored_image_count = coalesce(i.stored_image_count, 0),
    extracted_image_count = GREATEST(d.extracted_image_count, coalesce(i.stored_image_count, 0)),
    ocr_image_text_count = coalesce(i.ocr_image_text_count, 0),
    indexed_image_text_count = coalesce(i.indexed_image_text_count, 0),
    updated_at = now()
FROM documents target
LEFT JOIN chunk_stats c ON c.document_id = target.id
LEFT JOIN image_stats i ON i.document_id = target.id
WHERE d.id = target.id;

INSERT INTO schema_migrations (version, name)
VALUES (14, 'document_ingest_stats')
ON CONFLICT (version) DO NOTHING;
