UPDATE system_ai_provider_settings
   SET encrypted_admin_api_key = CASE
           WHEN %s::text IS NULL THEN ''
           WHEN %s::text = '' THEN ''
           ELSE encode(pgp_sym_encrypt(%s::text, %s::text), 'base64')
       END,
       admin_key_preview = %s,
       updated_by = %s,
       updated_at = now()
 WHERE provider_type_id = (SELECT id FROM ai_provider_types WHERE code = %s);
