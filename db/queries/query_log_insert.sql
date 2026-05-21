INSERT INTO query_logs (
    username,
    model_name,
    retrieval_strategy,
    question,
    retrieval_query,
    elapsed_ms,
    cache_hit,
    confidence_score
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id;
