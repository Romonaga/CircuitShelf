INSERT INTO response_cache_sources (
    cache_entry_id,
    rank,
    document_id,
    chunk_id,
    source_path,
    page_number,
    distance,
    preview,
    chunk_index,
    section_title,
    category,
    source_image_key
)
VALUES (
    %s,
    %s,
    (
        SELECT id
        FROM documents
        WHERE source_path = %s
           OR display_name = %s
        ORDER BY source_path
        LIMIT 1
    ),
    (
        SELECT c.id
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE (d.source_path = %s OR d.display_name = %s)
          AND c.chunk_index = %s
        LIMIT 1
    ),
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s
);
