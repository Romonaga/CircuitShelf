INSERT INTO conversations (username, title)
VALUES (%s, %s)
RETURNING id, username, title, created_at, updated_at;
