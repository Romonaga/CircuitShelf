SELECT dc.chunk_index,
       dc.chunk_text,
       dc.section_title,
       dc.category,
       dc.quality_score,
       dp.page_number,
       d.source_path,
       d.display_name
FROM assembly_plan_steps aps
JOIN assembly_plans ap ON ap.id = aps.plan_id
JOIN documents d ON d.source_path = aps.source_path
LEFT JOIN document_pages target_page
       ON target_page.document_id = d.id
      AND target_page.page_number = aps.page_number
JOIN document_chunks dc
      ON dc.document_id = d.id
     AND (
         aps.page_number IS NULL
         OR dc.page_id = target_page.id
     )
LEFT JOIN document_pages dp ON dp.id = dc.page_id
WHERE aps.id = %s
  AND aps.plan_id = %s
  AND (%s::bigint IS NULL OR ap.user_id = %s)
ORDER BY
    CASE dc.category
        WHEN 'TECH_LEVEL_DETAIL' THEN 0
        WHEN 'MED_LEVEL_DETAIL' THEN 1
        ELSE 2
    END,
    dc.quality_score DESC,
    dc.chunk_index
LIMIT %s;
