INSERT INTO document_intelligence_pins (
    intelligence_id,
    pin_number,
    label,
    function_text,
    page_number,
    source_chunk_index,
    evidence
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (intelligence_id, pin_number) DO UPDATE SET
    label = EXCLUDED.label,
    function_text = EXCLUDED.function_text,
    page_number = EXCLUDED.page_number,
    source_chunk_index = EXCLUDED.source_chunk_index,
    evidence = EXCLUDED.evidence;
