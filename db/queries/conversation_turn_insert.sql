WITH next_turn AS (
    SELECT coalesce(max(ordinal), 0) + 1 AS ordinal
    FROM conversation_turns
    WHERE conversation_id = %s
)
INSERT INTO conversation_turns (
    conversation_id,
    ordinal,
    question,
    answer_markdown,
    model_name,
    retrieval_strategy,
    confidence_score,
    response_snapshot
)
SELECT %s,
       next_turn.ordinal,
       %s,
       %s,
       %s,
       %s,
       %s,
       %s::jsonb
FROM next_turn
RETURNING id, ordinal, question, answer_markdown, model_name, retrieval_strategy, confidence_score, response_snapshot, created_at;
