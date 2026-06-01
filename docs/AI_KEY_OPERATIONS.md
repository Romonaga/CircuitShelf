# AI Key Operations

CircuitShelf stores OpenAI provider keys encrypted in Postgres with `pgcrypto`.
The encryption secret is runtime infrastructure, not an application setting.

## Secret Location

Set the key encryption secret with `AI_KEY_ENCRYPTION_SECRET`.

For the systemd service, put it in:

```bash
/etc/circuitshelf/circuitshelf.env
```

The service unit loads that file with `EnvironmentFile=-/etc/circuitshelf/circuitshelf.env`.
Keep the file owned by root and readable only by the service group.

Example shape:

```bash
AI_KEY_ENCRYPTION_SECRET=replace-with-a-long-random-secret
```

Legacy `config/config.yaml` secrets are still read with a warning so an older local install can boot, but new installs should not store provider-key encryption material in YAML.

## Backup

Back up encrypted provider-key rows before DB maintenance or secret rotation:

```bash
.venv/bin/python tools/ai_key_ops.py backup --output /secure/path/circuitshelf-ai-keys.json
```

The backup contains encrypted keys, previews, billing settings, key policies, assist mode, and default models. It is only useful with the matching `AI_KEY_ENCRYPTION_SECRET`, so keep both protected.

## Restore

Restore the encrypted rows into a migrated database:

```bash
.venv/bin/python tools/ai_key_ops.py restore --input /secure/path/circuitshelf-ai-keys.json
```

Restore does not decrypt keys. It writes the encrypted values back into the system, entity, and user provider settings tables.

## Rotate The Encryption Secret

Rotate when the infrastructure secret may be exposed or as scheduled maintenance:

```bash
AI_KEY_ENCRYPTION_SECRET_OLD=old-secret \
AI_KEY_ENCRYPTION_SECRET=new-secret \
.venv/bin/python tools/ai_key_ops.py rotate-secret
```

The command decrypts each stored provider key with the old secret and re-encrypts it with the new secret inside one database transaction. After the command succeeds, update `/etc/circuitshelf/circuitshelf.env` to the new secret and restart CircuitShelf.

Recommended order:

1. Run an AI key backup.
2. Generate a long random new secret.
3. Run `rotate-secret`.
4. Update the service environment file.
5. Restart CircuitShelf.
6. Test system, entity, and user OpenAI key paths from the UI.

Do not rotate the secret by editing the environment file alone. Existing encrypted rows will become unreadable until they are re-encrypted or restored from a backup made with the previous secret.
