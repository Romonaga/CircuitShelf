BEGIN;

UPDATE app_settings
   SET description = 'PaddleOCR CUDA lanes. Auto sizes from detected GPU count and VRAM, with 20GB+ GPUs allowed higher OCR concurrency.',
       updated_at = now()
 WHERE key = 'LOCAL_GPU_OCR_SLOTS';

INSERT INTO schema_migrations (version, name)
VALUES (64, 'describe_higher_ocr_lane_auto')
ON CONFLICT (version) DO NOTHING;

COMMIT;
