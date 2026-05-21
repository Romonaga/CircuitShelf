SELECT source_path AS path,
       size_bytes AS size,
       mtime_ns,
       sha256
FROM documents
WHERE status = 'indexed'
ORDER BY source_path;
