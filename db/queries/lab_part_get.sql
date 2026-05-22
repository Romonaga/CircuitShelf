SELECT p.id,
       p.user_id,
       p.display_name,
       p.normalized_name,
       p.part_type,
       p.quantity,
       p.location,
       p.notes,
       p.created_at,
       p.updated_at,
       COALESCE(
           array_agg(a.alias ORDER BY a.alias) FILTER (WHERE a.alias IS NOT NULL),
           ARRAY[]::text[]
       ) AS aliases
FROM lab_parts p
LEFT JOIN lab_part_aliases a ON a.part_id = p.id
WHERE p.id = %s
  AND p.user_id = %s
GROUP BY p.id;
