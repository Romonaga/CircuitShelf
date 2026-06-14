UPDATE ai_assist_events
   SET final_cost = %s,
       cost_status = %s,
       cost_discrepancy = %s,
       reconciliation_run_id = %s::uuid,
       allocation_method = %s
 WHERE id = %s;
