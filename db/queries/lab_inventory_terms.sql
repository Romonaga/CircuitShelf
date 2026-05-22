SELECT p.id AS part_id,
       p.display_name,
       p.normalized_name,
       p.part_type,
       p.quantity,
       p.location,
       p.notes,
       p.normalized_name AS normalized_term,
       p.display_name AS term
FROM lab_parts p
WHERE p.user_id = %s

UNION ALL

SELECT p.id AS part_id,
       p.display_name,
       p.normalized_name,
       p.part_type,
       p.quantity,
       p.location,
       p.notes,
       a.normalized_alias AS normalized_term,
       a.alias AS term
FROM lab_parts p
JOIN lab_part_aliases a ON a.part_id = p.id
WHERE p.user_id = %s;
