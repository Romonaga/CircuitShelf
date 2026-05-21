SELECT count(*) AS pending
FROM documents
WHERE status = 'needs_review';
