SELECT id, ordinal, note
FROM assembly_plan_power_notes
WHERE plan_id = %s
ORDER BY ordinal ASC;
