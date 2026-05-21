SELECT id,
       answer_markdown,
       confidence_score
FROM response_cache_entries
WHERE cache_key = %s
  AND index_fingerprint = %s
  AND model_name = %s
  AND retrieval_strategy = %s
  AND question = %s
  AND retrieval_query = %s
  AND top_k = %s
  AND distance_threshold = %s
  AND context_token_limit = %s
  AND show_full_text = %s;
