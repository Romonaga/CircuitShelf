BEGIN;

DELETE FROM app_settings
 WHERE key IN (
    'PADDLEOCR_USE_GPU',
    'PADDLEOCR_GPU_EXPERIMENTAL_ENABLED'
 );

UPDATE app_settings
   SET description = 'OCR engine used during ingestion: tesseract or paddleocr.',
       updated_at = now()
 WHERE key = 'OCR_ENGINE';

UPDATE app_settings
   SET description = 'PaddleOCR compute device when OCR_ENGINE is paddleocr: cpu or gpu.',
       updated_at = now()
 WHERE key = 'PADDLEOCR_DEVICE';

INSERT INTO schema_migrations (version, name)
VALUES (50, 'simplify_ocr_engine_settings')
ON CONFLICT (version) DO NOTHING;

COMMIT;
