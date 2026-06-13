SELECT source_path,
       display_name,
       chunk_index,
       page_number,
       section_title,
       category,
       quality_score,
       chunk_text,
       ARRAY[]::text[] AS matched_terms,
       0 AS matched_count
FROM (
    SELECT d.source_path,
           d.display_name,
           dc.chunk_index,
           dp.page_number,
           dc.section_title,
           dc.category,
           dc.quality_score,
           dc.chunk_text
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    LEFT JOIN document_pages dp ON dp.id = dc.page_id
    WHERE d.status_id = 3
      AND lower(dc.chunk_text) ~ %s
      AND (
          lower(dc.chunk_text) ~ '(project|experiment|circuit|build|breadboard|schematic|parts|components|wire|wiring)'
          OR dc.category IN ('MED_LEVEL_DETAIL', 'TECH_LEVEL_DETAIL', 'CODE_SAMPLE')
          OR lower(coalesce(dc.section_title, '')) LIKE 'code sample%%'
      )
) AS matched
ORDER BY quality_score DESC,
         source_path,
         page_number NULLS LAST,
         chunk_index
LIMIT %s;
