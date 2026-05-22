SELECT
    ap.id,
    ap.title,
    ap.objective,
    ap.component_name,
    ap.component_type,
    ap.confidence,
    ap.status,
    ap.created_at,
    ap.updated_at,
    count(aps.id) AS step_count,
    count(aps.id) FILTER (WHERE aps.completed_at IS NOT NULL) AS completed_step_count
FROM assembly_plans ap
LEFT JOIN assembly_plan_steps aps ON aps.plan_id = ap.id
GROUP BY ap.id
ORDER BY ap.updated_at DESC, ap.created_at DESC;
