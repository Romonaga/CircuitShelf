INSERT INTO user_preferences (
    user_id,
    preference_key,
    preference_value,
    updated_at
)
VALUES (%s, %s, %s::jsonb, now())
ON CONFLICT (user_id, preference_key) DO UPDATE SET
    preference_value = EXCLUDED.preference_value,
    updated_at = now()
RETURNING preference_value;
