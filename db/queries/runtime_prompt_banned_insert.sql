INSERT INTO prompt_security_banned_phrases (phrase)
VALUES (%s)
ON CONFLICT (phrase) DO NOTHING;
