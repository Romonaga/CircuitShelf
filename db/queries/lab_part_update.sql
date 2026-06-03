UPDATE lab_parts
SET display_name = %s,
    normalized_name = %s,
    part_type = %s,
    quantity = %s,
    location_id = %s,
    location = %s,
    notes = %s,
    updated_at = now()
WHERE id = %s
  AND user_id = %s
RETURNING id, user_id, display_name, normalized_name, part_type, quantity, location_id, location, notes, created_at, updated_at;
