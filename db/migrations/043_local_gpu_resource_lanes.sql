BEGIN;

ALTER TABLE local_gpu_work_items
    ADD COLUMN IF NOT EXISTS resource_class text NOT NULL DEFAULT 'local_llm';

UPDATE local_gpu_work_items
   SET resource_class = CASE
        WHEN task_type IN ('embedding', 'rerank') THEN 'cuda_batch'
        ELSE 'local_llm'
       END
 WHERE resource_class IS NULL
    OR resource_class = ''
    OR resource_class = 'local_llm';

DROP INDEX IF EXISTS idx_local_gpu_work_items_queue;

CREATE INDEX IF NOT EXISTS idx_local_gpu_work_items_queue
    ON local_gpu_work_items (resource_class, status, priority, id)
    WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS idx_local_gpu_work_items_resource_recent
    ON local_gpu_work_items (resource_class, created_at DESC);

INSERT INTO app_settings (key, value_type, text_value, description, updated_at)
VALUES
    (
        'LOCAL_GPU_LLM_SLOTS',
        'text',
        'auto',
        'Local LLM GPU slots. Auto means one local Ollama generation lane per detected GPU.',
        now()
    ),
    (
        'LOCAL_GPU_CUDA_SLOTS',
        'text',
        'auto',
        'CUDA batch work lanes for embedding and reranking. Auto uses a conservative per-GPU batch lane count.',
        now()
    )
ON CONFLICT (key) DO NOTHING;

DELETE FROM app_settings
 WHERE key = 'LOCAL_GPU_QUEUE_SLOTS';

INSERT INTO schema_migrations (version, name)
VALUES (43, 'local_gpu_resource_lanes')
ON CONFLICT (version) DO NOTHING;

COMMIT;
