SELECT
    (SELECT id FROM ai_provider_types WHERE code = %s) AS provider_type_id,
    (SELECT id FROM ai_assist_modes WHERE code = %s) AS assist_mode_id,
    (SELECT id FROM ai_key_policies WHERE code = %s) AS key_policy_id;
