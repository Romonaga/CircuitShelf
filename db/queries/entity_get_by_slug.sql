SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at
FROM entities
WHERE slug = %s;
