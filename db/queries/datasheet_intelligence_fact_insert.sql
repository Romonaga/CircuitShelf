INSERT INTO document_intelligence_facts (
    intelligence_id,
    fact_type,
    label,
    value,
    unit,
    page_number,
    source_chunk_index,
    evidence,
    confidence
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
