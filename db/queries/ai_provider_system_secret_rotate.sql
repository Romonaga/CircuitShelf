UPDATE system_ai_provider_settings
SET encrypted_api_key = encode(
        pgp_sym_encrypt(
            pgp_sym_decrypt(decode(encrypted_api_key, 'base64'), %s::text),
            %s::text
        ),
        'base64'
    ),
    updated_at = now()
WHERE encrypted_api_key <> '';
