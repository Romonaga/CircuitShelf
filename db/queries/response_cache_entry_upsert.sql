INSERT INTO response_cache_entries (
    cache_key,
    index_fingerprint,
    model_name,
    retrieval_strategy,
    question,
    retrieval_query,
    top_k,
    distance_threshold,
    context_token_limit,
    show_full_text,
    answer_markdown,
    confidence_score,
    last_accessed_at,
    hit_count
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), 0)
ON CONFLICT (cache_key) DO UPDATE SET
    index_fingerprint = EXCLUDED.index_fingerprint,
    model_name = EXCLUDED.model_name,
    retrieval_strategy = EXCLUDED.retrieval_strategy,
    question = EXCLUDED.question,
    retrieval_query = EXCLUDED.retrieval_query,
    top_k = EXCLUDED.top_k,
    distance_threshold = EXCLUDED.distance_threshold,
    context_token_limit = EXCLUDED.context_token_limit,
    show_full_text = EXCLUDED.show_full_text,
    answer_markdown = EXCLUDED.answer_markdown,
    confidence_score = EXCLUDED.confidence_score,
    last_accessed_at = now()
RETURNING id;
