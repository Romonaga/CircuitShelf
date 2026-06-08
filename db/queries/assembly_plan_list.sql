SELECT
    ap.id,
    ap.title,
    ap.objective,
    ap.component_name,
    ap.component_type,
    ap.confidence,
    statuses.code AS status,
    ap.status_id,
    ap.user_id,
    ap.created_by,
    ap.created_at,
    ap.updated_at,
    count(aps.id) AS step_count,
    count(aps.id) FILTER (WHERE aps.completed_at IS NOT NULL) AS completed_step_count
FROM assembly_plans ap
JOIN assembly_plan_statuses statuses ON statuses.id = ap.status_id
LEFT JOIN assembly_plan_steps aps ON aps.plan_id = ap.id
WHERE (%s::bigint IS NULL OR ap.user_id = %s::bigint)
GROUP BY ap.id, statuses.code
ORDER BY ap.updated_at DESC, ap.created_at DESC;
