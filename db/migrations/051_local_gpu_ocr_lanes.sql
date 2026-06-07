BEGIN;

INSERT INTO app_settings (key, value_type, text_value, description, updated_at)
VALUES
    (
        'LOCAL_GPU_OCR_SLOTS',
        'text',
        'auto',
        'PaddleOCR CUDA lanes. Auto allows more OCR page workers than model-generation lanes while keeping ingestion lower priority.',
        now()
    )
ON CONFLICT (key) DO NOTHING;

UPDATE local_gpu_work_items
   SET resource_class = 'ocr_cuda'
 WHERE task_type = 'paddleocr'
   AND resource_class <> 'ocr_cuda';

INSERT INTO schema_migrations (version, name)
VALUES (51, 'local_gpu_ocr_lanes')
ON CONFLICT (version) DO NOTHING;

COMMIT;
