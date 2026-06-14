UPDATE ai_cost_reconciliation_runs
   SET status = 'failed',
       error_message = %s,
       completed_at = now()
 WHERE id = %s::uuid;
