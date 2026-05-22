WITH terms AS (
    SELECT DISTINCT lower(term) AS term
    FROM unnest(%s::text[]) AS term
    WHERE length(trim(term)) >= 2
)
SELECT d.source_path,
       d.display_name,
       di.component_name,
       di.component_type,
       di.summary,
       di.confidence,
       array_agg(DISTINCT terms.term ORDER BY terms.term) AS matched_terms,
       count(DISTINCT terms.term) AS matched_count
FROM document_intelligence di
JOIN documents d ON d.id = di.document_id
JOIN terms ON lower(COALESCE(di.component_name, '') || ' ' || COALESCE(di.component_type, '') || ' ' || d.display_name) LIKE '%%' || terms.term || '%%'
WHERE d.status = 'indexed'
GROUP BY d.source_path,
         d.display_name,
         di.component_name,
         di.component_type,
         di.summary,
         di.confidence
ORDER BY matched_count DESC,
         di.confidence DESC,
         d.display_name
LIMIT %s;
