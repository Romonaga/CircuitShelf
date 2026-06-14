UPDATE ai_assist_events
   SET estimated_cost = %s
 WHERE id = %s
RETURNING id;
