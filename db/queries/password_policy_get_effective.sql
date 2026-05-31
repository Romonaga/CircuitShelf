SELECT pp.id,
       pp.entity_id,
       pp.min_length,
       pp.require_upper,
       pp.require_lower,
       pp.require_number,
       pp.require_symbol,
       pp.password_change_days,
       pp.max_failed_attempts,
       pp.lockout_minutes,
       pp.updated_at
FROM password_policies pp
WHERE pp.entity_id = %s
   OR pp.entity_id IS NULL
ORDER BY pp.entity_id NULLS LAST
LIMIT 1;
