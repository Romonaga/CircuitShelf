SELECT pin_number,
       label,
       function_text,
       page_number,
       source_chunk_index,
       evidence
FROM document_intelligence_pins
WHERE intelligence_id = %s
ORDER BY pin_number;
