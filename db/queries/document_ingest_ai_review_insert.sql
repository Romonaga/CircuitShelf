INSERT INTO document_ingest_ai_reviews (
    source_path,
    provider_type_id,
    model_name,
    paid_by,
    review_text,
    review_json,
    estimated_cost
)
VALUES (
    %s,
    (SELECT id FROM ai_provider_types WHERE code = %s),
    %s,
    %s,
    %s,
    %s::jsonb,
    %s
)
RETURNING id;
