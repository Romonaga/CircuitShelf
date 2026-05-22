SELECT fact_type,
       label,
       value,
       unit,
       page_number,
       source_chunk_index,
       evidence,
       confidence
FROM document_intelligence_facts
WHERE intelligence_id = %s
ORDER BY fact_type, page_number NULLS LAST, label, value;
