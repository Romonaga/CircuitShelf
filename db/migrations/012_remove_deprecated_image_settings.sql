BEGIN;

DELETE FROM app_settings
WHERE key IN (
    'SAVE_EXTRACTED_IMAGES',
    'EXTRACTED_IMAGES_DIR'
);

INSERT INTO schema_migrations (version, name)
VALUES (12, 'remove_deprecated_image_settings')
ON CONFLICT (version) DO NOTHING;

COMMIT;
