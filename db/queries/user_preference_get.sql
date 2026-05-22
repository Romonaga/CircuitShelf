SELECT preference_value
FROM user_preferences
WHERE user_id = %s
  AND preference_key = %s;
