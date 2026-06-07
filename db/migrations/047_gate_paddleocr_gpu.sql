BEGIN;

UPDATE app_settings
   SET boolean_value = false,
       description = 'Request PaddleOCR GPU inference when OCR_ENGINE is paddleocr. Requires the experimental GPU gate.',
       updated_at = now()
 WHERE key = 'PADDLEOCR_USE_GPU';

UPDATE app_settings
   SET text_value = 'cpu',
       description = 'PaddleOCR device hint: gpu or cpu. GPU is ignored unless the experimental GPU gate is enabled.',
       updated_at = now()
 WHERE key = 'PADDLEOCR_DEVICE';

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
VALUES (
    'PADDLEOCR_GPU_EXPERIMENTAL_ENABLED',
    'boolean',
    NULL,
    NULL,
    NULL,
    false,
    'Allow PaddleOCR to use CUDA. Keep off unless actively testing GPU OCR stability.',
    false
)
ON CONFLICT (key) DO UPDATE
SET boolean_value = false,
    description = EXCLUDED.description,
    updated_at = now();

INSERT INTO schema_migrations (version, name)
VALUES (47, 'gate_paddleocr_gpu')
ON CONFLICT (version) DO NOTHING;

COMMIT;
