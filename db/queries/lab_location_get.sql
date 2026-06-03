SELECT id,
       user_id,
       display_name,
       normalized_name,
       notes,
       created_at,
       updated_at
FROM lab_locations
WHERE id = %s
  AND user_id = %s;
