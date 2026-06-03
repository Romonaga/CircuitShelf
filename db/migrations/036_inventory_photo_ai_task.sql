BEGIN;

INSERT INTO ai_task_types (id, code, display_name, description)
VALUES (6, 'inventory_photo_import', 'Inventory photo import', 'Identify lab inventory parts from uploaded photos.')
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description;

INSERT INTO schema_migrations (version, name)
VALUES (36, 'inventory_photo_ai_task')
ON CONFLICT (version) DO NOTHING;

COMMIT;
