INSERT INTO performance_resource_samples (
    sampled_at,
    cpu_percent,
    cpu_temperature_c,
    cpu_power_w,
    process_cpu_percent,
    process_memory_bytes,
    process_threads,
    system_memory_used_percent,
    gpu_percent,
    gpu_memory_used_percent,
    gpu_memory_used_mib,
    gpu_memory_total_mib,
    gpu_temperature_c,
    gpu_power_w,
    active_document_workers,
    embedding_batch_active,
    reranker_batch_active,
    chunks,
    sources,
    image_ids
)
VALUES (
    now(),
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s
);
