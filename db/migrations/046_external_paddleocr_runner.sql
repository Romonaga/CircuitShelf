BEGIN;

INSERT INTO app_settings (
    key,
    value_type,
    text_value,
    integer_value,
    numeric_value,
    boolean_value,
    description,
    is_sensitive
)
VALUES
    ('PADDLEOCR_PYTHON', 'text', '', NULL, NULL, NULL, 'Optional Python executable for an isolated PaddleOCR environment.', false),
    ('PADDLEOCR_TIMEOUT_SECONDS', 'integer', NULL, 120, NULL, NULL, 'Seconds allowed for one PaddleOCR image request before falling back.', false)
ON CONFLICT (key) DO NOTHING;

INSERT INTO schema_migrations (version, name)
VALUES (46, 'external_paddleocr_runner')
ON CONFLICT (version) DO NOTHING;

COMMIT;
