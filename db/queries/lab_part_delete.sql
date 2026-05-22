DELETE FROM lab_parts
WHERE id = %s
  AND user_id = %s
RETURNING id;
