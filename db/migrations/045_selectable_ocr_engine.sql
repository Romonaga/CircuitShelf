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
    ('OCR_ENGINE', 'text', 'tesseract', NULL, NULL, NULL, 'OCR engine used during ingestion: tesseract or paddleocr.', false),
    ('OCR_ENGINE_FALLBACK', 'boolean', NULL, NULL, NULL, true, 'Fall back to Tesseract when the selected OCR engine is unavailable or fails.', false),
    ('PADDLEOCR_USE_GPU', 'boolean', NULL, NULL, NULL, true, 'Use PaddleOCR GPU inference when OCR_ENGINE is paddleocr.', false),
    ('PADDLEOCR_DEVICE', 'text', 'gpu', NULL, NULL, NULL, 'PaddleOCR device hint: gpu or cpu.', false),
    ('PADDLEOCR_LANG', 'text', 'en', NULL, NULL, NULL, 'PaddleOCR recognition language code.', false),
    ('PADDLEOCR_ENGINE', 'text', '', NULL, NULL, NULL, 'Optional PaddleOCR inference backend override. Leave blank for PaddleOCR defaults.', false)
ON CONFLICT (key) DO NOTHING;

INSERT INTO schema_migrations (version, name)
VALUES (45, 'selectable_ocr_engine')
ON CONFLICT (version) DO NOTHING;

COMMIT;
