INSERT INTO lab_locations (
    user_id,
    display_name,
    normalized_name,
    notes,
    updated_at
)
VALUES (%s, %s, %s, %s, now())
ON CONFLICT (user_id, normalized_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    notes = CASE
        WHEN EXCLUDED.notes <> '' THEN EXCLUDED.notes
        ELSE lab_locations.notes
    END,
    updated_at = now()
RETURNING id, user_id, display_name, normalized_name, notes, created_at, updated_at;
