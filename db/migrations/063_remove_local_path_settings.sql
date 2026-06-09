BEGIN;

DELETE FROM app_settings
WHERE key IN (
    'PADDLEOCR_PYTHON',
    'TESSERACT_CMD'
);

INSERT INTO schema_migrations (version, name)
VALUES (63, 'remove_local_path_settings')
ON CONFLICT (version) DO NOTHING;

COMMIT;
