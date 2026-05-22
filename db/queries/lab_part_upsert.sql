INSERT INTO lab_parts (
    user_id,
    display_name,
    normalized_name,
    part_type,
    quantity,
    location,
    notes,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, now())
ON CONFLICT (user_id, normalized_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    part_type = EXCLUDED.part_type,
    quantity = EXCLUDED.quantity,
    location = EXCLUDED.location,
    notes = EXCLUDED.notes,
    updated_at = now()
RETURNING id, user_id, display_name, normalized_name, part_type, quantity, location, notes, created_at, updated_at;
