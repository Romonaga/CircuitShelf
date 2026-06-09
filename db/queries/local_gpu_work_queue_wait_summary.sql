WITH recent AS (
    SELECT work.resource_class,
           statuses.code AS status,
           work.created_at,
           work.wait_seconds
      FROM local_gpu_work_items work
      JOIN local_gpu_work_statuses statuses ON statuses.id = work.status_id
     WHERE work.status_id IN (1, 2)
        OR work.created_at >= now() - (%s::text)::interval
),
resource_summary AS (
    SELECT resource_class,
           count(*) FILTER (WHERE status = 'queued') AS queued,
           count(*) FILTER (WHERE status = 'running') AS running,
           avg(extract(epoch FROM (now() - created_at))) FILTER (WHERE status = 'queued') AS current_avg_wait_seconds,
           max(extract(epoch FROM (now() - created_at))) FILTER (WHERE status = 'queued') AS current_max_wait_seconds,
           avg(wait_seconds) FILTER (WHERE wait_seconds IS NOT NULL) AS recent_avg_wait_seconds,
           max(wait_seconds) FILTER (WHERE wait_seconds IS NOT NULL) AS recent_max_wait_seconds
      FROM recent
     GROUP BY resource_class
),
overall_summary AS (
    SELECT 'all'::text AS resource_class,
           count(*) FILTER (WHERE status = 'queued') AS queued,
           count(*) FILTER (WHERE status = 'running') AS running,
           avg(extract(epoch FROM (now() - created_at))) FILTER (WHERE status = 'queued') AS current_avg_wait_seconds,
           max(extract(epoch FROM (now() - created_at))) FILTER (WHERE status = 'queued') AS current_max_wait_seconds,
           avg(wait_seconds) FILTER (WHERE wait_seconds IS NOT NULL) AS recent_avg_wait_seconds,
           max(wait_seconds) FILTER (WHERE wait_seconds IS NOT NULL) AS recent_max_wait_seconds
      FROM recent
)
SELECT resource_class,
       queued,
       running,
       current_avg_wait_seconds,
       current_max_wait_seconds,
       recent_avg_wait_seconds,
       recent_max_wait_seconds
  FROM resource_summary
UNION ALL
SELECT resource_class,
       queued,
       running,
       current_avg_wait_seconds,
       current_max_wait_seconds,
       recent_avg_wait_seconds,
       recent_max_wait_seconds
  FROM overall_summary
 ORDER BY resource_class;
