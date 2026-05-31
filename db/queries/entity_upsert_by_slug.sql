INSERT INTO entities (name, slug, owner_user_id)
VALUES (%s, %s, %s)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    owner_user_id = coalesce(entities.owner_user_id, EXCLUDED.owner_user_id),
    is_active = true,
    updated_at = now()
RETURNING id, name, slug, owner_user_id, is_active, created_at, updated_at;
