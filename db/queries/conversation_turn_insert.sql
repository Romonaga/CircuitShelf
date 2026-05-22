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
    confidence_score
)
SELECT %s,
       next_turn.ordinal,
       %s,
       %s,
       %s,
       %s,
       %s
FROM next_turn
RETURNING id, ordinal, question, answer_markdown, created_at;
