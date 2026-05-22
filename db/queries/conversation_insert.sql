INSERT INTO conversations (user_id, username, title)
SELECT %s, username, %s
FROM users
WHERE id = %s
RETURNING id, user_id, username, title, created_at, updated_at;
