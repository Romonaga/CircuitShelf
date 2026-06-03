SELECT p.id AS part_id,
       p.display_name,
       p.normalized_name,
       p.part_type,
       p.quantity,
       COALESCE(l.display_name, p.location, '') AS location,
       p.notes,
       p.normalized_name AS normalized_term,
       p.display_name AS term
FROM lab_parts p
LEFT JOIN lab_locations l ON l.id = p.location_id
WHERE p.user_id = %s

UNION ALL

SELECT p.id AS part_id,
       p.display_name,
       p.normalized_name,
       p.part_type,
       p.quantity,
       COALESCE(l.display_name, p.location, '') AS location,
       p.notes,
       a.normalized_alias AS normalized_term,
       a.alias AS term
FROM lab_parts p
LEFT JOIN lab_locations l ON l.id = p.location_id
JOIN lab_part_aliases a ON a.part_id = p.id
WHERE p.user_id = %s;
