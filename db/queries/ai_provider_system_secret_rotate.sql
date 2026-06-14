UPDATE system_ai_provider_settings
SET encrypted_api_key = CASE
        WHEN encrypted_api_key = '' THEN encrypted_api_key
        ELSE encode(
            pgp_sym_encrypt(
                pgp_sym_decrypt(decode(encrypted_api_key, 'base64'), %s::text),
                %s::text
            ),
            'base64'
        )
    END,
    encrypted_admin_api_key = CASE
        WHEN encrypted_admin_api_key = '' THEN encrypted_admin_api_key
        ELSE encode(
            pgp_sym_encrypt(
                pgp_sym_decrypt(decode(encrypted_admin_api_key, 'base64'), %s::text),
                %s::text
            ),
            'base64'
        )
    END,
    updated_at = now()
WHERE encrypted_api_key <> ''
   OR encrypted_admin_api_key <> '';
