INSERT INTO chunk_quality_flags (chunk_id, flag)
VALUES (%s, %s)
ON CONFLICT (chunk_id, flag) DO NOTHING;
