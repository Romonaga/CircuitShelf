SELECT id,
       ordinal,
       question,
       answer_markdown,
       model_name,
       retrieval_strategy,
       confidence_score,
       response_snapshot,
       created_at
FROM conversation_turns
WHERE conversation_id = %s
ORDER BY ordinal;
