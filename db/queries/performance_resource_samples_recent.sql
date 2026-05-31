SELECT sampled_at,
       cpu_percent,
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
FROM performance_resource_samples
WHERE sampled_at >= now() - (%s::integer * interval '1 hour')
ORDER BY sampled_at DESC
LIMIT %s;
