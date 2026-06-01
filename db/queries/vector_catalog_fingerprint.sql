SELECT coalesce(
    string_agg(
        source_path || '|' || size_bytes || '|' || mtime_ns || '|' || coalesce(sha256, ''),
        E'\n'
        ORDER BY source_path
    ),
    ''
) AS fingerprint_source
FROM documents
WHERE status = 'indexed'
  AND document_visible_to_entity(is_global, entity_id, %s::bigint);
