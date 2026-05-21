INSERT INTO response_cache_chat_turns (
    cache_entry_id,
    turn_index,
    user_message,
    assistant_message
)
VALUES (%s, %s, %s, %s);
