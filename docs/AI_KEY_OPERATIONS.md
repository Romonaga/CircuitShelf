# AI Key Operations

CircuitShelf stores OpenAI provider keys encrypted in Postgres with `pgcrypto`.
The encryption secret is runtime infrastructure, not an application setting.

## Secret Location

Store the key encryption secret in an OS-protected file. By default CircuitShelf reads:

```bash
/etc/circuitshelf/ai-key-encryption.secret
```

The file should contain only the secret value, with no `KEY=` prefix:

```bash
replace-with-a-long-random-secret
```

Keep the file owned by root and readable only by the service group:

```bash
sudo install -d -m 750 -o root -g hellweek /etc/circuitshelf
openssl rand -base64 48 | sudo tee /etc/circuitshelf/ai-key-encryption.secret >/dev/null
sudo chown root:hellweek /etc/circuitshelf/ai-key-encryption.secret
sudo chmod 640 /etc/circuitshelf/ai-key-encryption.secret
```

If you need a non-default path, set `AI_KEY_ENCRYPTION_SECRET_FILE` in `config/config.yaml`.

`AI_KEY_ENCRYPTION_SECRET` in the process environment and legacy YAML secrets are still read as compatibility fallbacks with warnings. New installs should not use them.

## Backup

Back up encrypted provider-key rows before DB maintenance or secret rotation:

```bash
.venv/bin/python tools/ai_key_ops.py backup --output /secure/path/circuitshelf-ai-keys.json
```

The backup contains encrypted keys, previews, billing settings, key policies, assist mode, and default models. It is only useful with the matching AI key encryption secret file, so keep both protected.

## Restore

Restore the encrypted rows into a migrated database:

```bash
.venv/bin/python tools/ai_key_ops.py restore --input /secure/path/circuitshelf-ai-keys.json
```

Restore does not decrypt keys. It writes the encrypted values back into the system, entity, and user provider settings tables.

## Rotate The Encryption Secret

Rotate when the infrastructure secret may be exposed or as scheduled maintenance:

```bash
.venv/bin/python tools/ai_key_ops.py rotate-secret \
  --old-secret-file /secure/path/old-ai-key-encryption.secret \
  --new-secret-file /secure/path/new-ai-key-encryption.secret
```

The command decrypts each stored provider key with the old secret and re-encrypts it with the new secret inside one database transaction. After the command succeeds, install the new secret at `/etc/circuitshelf/ai-key-encryption.secret` and restart CircuitShelf.

Recommended order:

1. Run an AI key backup.
2. Generate a long random new secret.
3. Run `rotate-secret`.
4. Install the new secret file.
5. Restart CircuitShelf.
6. Test system, entity, and user OpenAI key paths from the UI.

Do not rotate the secret by replacing the file alone. Existing encrypted rows will become unreadable until they are re-encrypted or restored from a backup made with the previous secret.
