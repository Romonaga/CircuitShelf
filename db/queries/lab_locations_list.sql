SELECT id,
       user_id,
       display_name,
       normalized_name,
       notes,
       created_at,
       updated_at
FROM lab_locations
WHERE user_id = %s
ORDER BY lower(display_name);
