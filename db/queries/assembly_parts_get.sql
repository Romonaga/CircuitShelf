SELECT id, ordinal, name, detail
FROM assembly_plan_parts
WHERE plan_id = %s
ORDER BY ordinal ASC;
