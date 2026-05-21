SELECT user_message,
       assistant_message
FROM response_cache_chat_turns
WHERE cache_entry_id = %s
ORDER BY turn_index;
