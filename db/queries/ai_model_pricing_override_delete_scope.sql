DELETE FROM ai_model_pricing_overrides o
USING ai_provider_types p, ai_billing_scope_types bst
WHERE o.provider_type_id = p.id
  AND o.billing_scope_type_id = bst.id
  AND p.code = %s
  AND bst.code = %s
  AND (%s::bigint IS NULL OR o.entity_id = %s::bigint)
  AND (%s::bigint IS NULL OR o.user_id = %s::bigint);
