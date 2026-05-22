INSERT INTO lab_part_aliases (part_id, alias, normalized_alias)
VALUES (%s, %s, %s)
ON CONFLICT (part_id, normalized_alias) DO NOTHING;
