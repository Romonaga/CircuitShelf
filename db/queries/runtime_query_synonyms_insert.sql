INSERT INTO query_synonyms (canonical_term, synonym)
VALUES (%s, %s)
ON CONFLICT (canonical_term, synonym) DO NOTHING;
