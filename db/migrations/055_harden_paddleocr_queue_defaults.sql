BEGIN;

UPDATE app_settings
   SET description = 'PaddleOCR CUDA lanes. Auto uses a conservative per-GPU lane count; explicit values can be used for tuning.',
       updated_at = now()
 WHERE key = 'LOCAL_GPU_OCR_SLOTS';

INSERT INTO schema_migrations (version, name)
VALUES (55, 'harden_paddleocr_queue_defaults')
ON CONFLICT (version) DO NOTHING;

COMMIT;
