BEGIN;

UPDATE app_settings
   SET text_value = 'gpu',
       updated_at = now()
 WHERE key = 'PADDLEOCR_DEVICE';

UPDATE app_settings
   SET boolean_value = true,
       updated_at = now()
 WHERE key = 'OCR_ENGINE_FALLBACK';

UPDATE app_settings
   SET description = 'Choose Tesseract CPU for stable OCR or PaddleOCR GPU for faster OCR with automatic Tesseract fallback.',
       updated_at = now()
 WHERE key = 'OCR_ENGINE';

UPDATE app_settings
   SET description = 'Internal safety setting. PaddleOCR always falls back to Tesseract when unavailable or failed.',
       updated_at = now()
 WHERE key = 'OCR_ENGINE_FALLBACK';

UPDATE app_settings
   SET description = 'Internal setting. CircuitShelf uses PaddleOCR on GPU only; CPU PaddleOCR is not exposed because this host falls back to Tesseract.',
       updated_at = now()
 WHERE key = 'PADDLEOCR_DEVICE';

INSERT INTO schema_migrations (version, name)
VALUES (52, 'paddle_gpu_only_ocr')
ON CONFLICT (version) DO NOTHING;

COMMIT;
