SELECT source_path AS path,
       size_bytes AS size,
       mtime_ns,
       sha256
FROM documents
WHERE status_id IN (2, 3)
ORDER BY source_path;
