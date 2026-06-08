SELECT
    plans.id,
    plans.title,
    plans.objective,
    plans.component_name,
    plans.component_type,
    plans.summary,
    plans.confidence,
    statuses.code AS status,
    plans.status_id,
    plans.user_id,
    plans.created_by,
    plans.created_at,
    plans.updated_at
FROM assembly_plans plans
JOIN assembly_plan_statuses statuses ON statuses.id = plans.status_id
WHERE plans.id = %s
  AND (%s::bigint IS NULL OR plans.user_id = %s::bigint);
