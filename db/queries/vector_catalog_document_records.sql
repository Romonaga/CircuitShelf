SELECT source_path AS path,
       size_bytes AS size,
       mtime_ns,
       sha256
FROM documents
WHERE status IN ('indexed', 'needs_review')
ORDER BY source_path;
