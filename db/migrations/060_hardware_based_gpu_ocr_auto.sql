BEGIN;

UPDATE app_settings
   SET description = 'PaddleOCR CUDA lanes. Auto sizes from detected GPU count and VRAM; explicit values can be used for tuning.',
       updated_at = now()
 WHERE key = 'LOCAL_GPU_OCR_SLOTS';

INSERT INTO schema_migrations (version, name)
VALUES (60, 'hardware_based_gpu_ocr_auto')
ON CONFLICT (version) DO NOTHING;

COMMIT;
