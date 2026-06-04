WITH bucketed AS (
    SELECT to_timestamp(floor(extract(epoch FROM sampled_at) / %s::integer) * %s::integer) AS sampled_at,
           max(cpu_percent) AS cpu_percent,
           max(cpu_temperature_c) AS cpu_temperature_c,
           max(cpu_power_w) AS cpu_power_w,
           max(process_cpu_percent) AS process_cpu_percent,
           max(process_memory_bytes) AS process_memory_bytes,
           max(process_threads) AS process_threads,
           max(system_memory_used_percent) AS system_memory_used_percent,
           max(gpu_percent) AS gpu_percent,
           max(gpu_memory_used_percent) AS gpu_memory_used_percent,
           max(gpu_memory_used_mib) AS gpu_memory_used_mib,
           max(gpu_memory_total_mib) AS gpu_memory_total_mib,
           max(gpu_temperature_c) AS gpu_temperature_c,
           max(gpu_power_w) AS gpu_power_w,
           max(active_document_workers) AS active_document_workers,
           max(active_document_worker_capacity) AS active_document_worker_capacity,
           max(embedding_batch_active) AS embedding_batch_active,
           max(reranker_batch_active) AS reranker_batch_active,
           max(chunks) AS chunks,
           max(sources) AS sources,
           max(image_ids) AS image_ids
    FROM performance_resource_samples
    WHERE sampled_at >= now() - (%s::integer * interval '1 hour')
    GROUP BY 1
)
SELECT sampled_at,
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
       active_document_worker_capacity,
       embedding_batch_active,
       reranker_batch_active,
       chunks,
       sources,
       image_ids
FROM bucketed
ORDER BY sampled_at DESC
LIMIT %s;
