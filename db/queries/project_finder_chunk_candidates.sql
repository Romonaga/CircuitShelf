WITH terms AS (
    SELECT DISTINCT lower(term) AS term
    FROM unnest(%s::text[]) AS term
    WHERE length(trim(term)) >= 2
),
matched AS (
    SELECT d.source_path,
           d.display_name,
           dc.chunk_index,
           dp.page_number,
           dc.section_title,
           dc.category,
           dc.quality_score,
           dc.chunk_text,
           array_agg(DISTINCT terms.term ORDER BY terms.term) AS matched_terms,
           count(DISTINCT terms.term) AS matched_count
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    LEFT JOIN document_pages dp ON dp.id = dc.page_id
    JOIN terms ON lower(dc.chunk_text) LIKE '%%' || terms.term || '%%'
    WHERE d.status = 'indexed'
      AND (
          lower(dc.chunk_text) ~ '(project|experiment|circuit|build|breadboard|schematic|parts|components|wire|wiring)'
          OR dc.category IN ('MED_LEVEL_DETAIL', 'TECH_LEVEL_DETAIL')
      )
    GROUP BY d.source_path,
             d.display_name,
             dc.chunk_index,
             dp.page_number,
             dc.section_title,
             dc.category,
             dc.quality_score,
             dc.chunk_text
)
SELECT source_path,
       display_name,
       chunk_index,
       page_number,
       section_title,
       category,
       quality_score,
       chunk_text,
       matched_terms,
       matched_count
FROM matched
ORDER BY matched_count DESC,
         quality_score DESC,
         source_path,
         page_number NULLS LAST,
         chunk_index
LIMIT %s;
