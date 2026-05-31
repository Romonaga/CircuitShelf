INSERT INTO password_policies (
    entity_id,
    min_length,
    require_upper,
    require_lower,
    require_number,
    require_symbol,
    password_change_days,
    max_failed_attempts,
    lockout_minutes,
    updated_by,
    updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
ON CONFLICT (entity_id) DO UPDATE SET
    min_length = EXCLUDED.min_length,
    require_upper = EXCLUDED.require_upper,
    require_lower = EXCLUDED.require_lower,
    require_number = EXCLUDED.require_number,
    require_symbol = EXCLUDED.require_symbol,
    password_change_days = EXCLUDED.password_change_days,
    max_failed_attempts = EXCLUDED.max_failed_attempts,
    lockout_minutes = EXCLUDED.lockout_minutes,
    updated_by = EXCLUDED.updated_by,
    updated_at = now()
RETURNING id,
          entity_id,
          min_length,
          require_upper,
          require_lower,
          require_number,
          require_symbol,
          password_change_days,
          max_failed_attempts,
          lockout_minutes,
          updated_at;
