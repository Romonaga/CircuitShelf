BEGIN;

ALTER TABLE document_images
    DROP COLUMN IF EXISTS image_path;

DELETE FROM app_settings
WHERE key IN (
    'SAVE_EXTRACTED_IMAGES',
    'EXTRACTED_IMAGES_DIR'
);

INSERT INTO schema_migrations (version, name)
VALUES (11, 'remove_disk_image_storage')
ON CONFLICT (version) DO NOTHING;

COMMIT;
