#!/usr/bin/env python3
"""Store an OpenAI key at system, entity, and/or user scope.

The key is read from stdin so it does not appear in shell history.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import psycopg
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.ai_key_secret import load_ai_key_encryption_secret  # noqa: E402

CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def read_key(prompt: bool) -> str:
    if prompt or sys.stdin.isatty():
        return getpass.getpass("OpenAI API key: ").strip()
    return sys.stdin.readline().strip()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Store an encrypted OpenAI API key.")
    p.add_argument("--user", default="hellweek", help="Username for user-scoped key.")
    p.add_argument("--entity", default="blaise-works", help="Entity slug for entity-scoped key.")
    p.add_argument("--model", default="gpt-5-chat-latest", help="Default model name.")
    p.add_argument("--system", action="store_true", help="Set system-level key.")
    p.add_argument("--entity-scope", action="store_true", help="Set entity-level key.")
    p.add_argument("--user-scope", action="store_true", help="Set user-level key.")
    p.add_argument("--all", action="store_true", help="Set system, entity, and user keys.")
    p.add_argument("--prompt", action="store_true", help="Prompt for the key instead of reading stdin.")
    return p


def main() -> int:
    args = parser().parse_args()
    scopes = {
        "system": bool(args.system or args.all),
        "entity": bool(args.entity_scope or args.all),
        "user": bool(args.user_scope or args.all),
    }
    if not any(scopes.values()):
        print("Choose at least one scope or use --all.", file=sys.stderr)
        return 2

    api_key = read_key(args.prompt)
    if not api_key:
        print("No key supplied.", file=sys.stderr)
        return 2

    config = load_config()
    database_url = os.environ.get("DATABASE_URL") or config.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is missing from the environment or config/config.yaml.", file=sys.stderr)
        return 2
    secret = load_ai_key_encryption_secret(config=config)
    preview = f"{api_key[:7]}...{api_key[-4:]}"

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            provider_id = cur.execute("select id from ai_provider_types where code = 'openai'").fetchone()[0]
            assist_mode_id = cur.execute("select id from ai_assist_modes where code = 'auto'").fetchone()[0]
            entity_policy_id = cur.execute("select id from ai_key_policies where code = 'entity'").fetchone()[0]
            user_policy_id = cur.execute("select id from ai_key_policies where code = 'user_when_available'").fetchone()[0]
            user_row = cur.execute("select id from users where username = %s", (args.user,)).fetchone()
            entity_row = cur.execute("select id from entities where slug = %s", (args.entity,)).fetchone()
            if scopes["user"] and not user_row:
                print(f"User not found: {args.user}", file=sys.stderr)
                return 2
            if scopes["entity"] and not entity_row:
                print(f"Entity not found: {args.entity}", file=sys.stderr)
                return 2
            user_id = int(user_row[0]) if user_row else None
            entity_id = int(entity_row[0]) if entity_row else None

            encrypted_expr = "encode(pgp_sym_encrypt(%s, %s), 'base64')"
            if scopes["system"]:
                cur.execute(
                    f"""
                    insert into system_ai_provider_settings
                        (provider_type_id, enabled, encrypted_api_key, key_preview, assist_mode_id, default_model, updated_by, updated_at)
                    values (%s, true, {encrypted_expr}, %s, %s, %s, %s, now())
                    on conflict (provider_type_id) do update set
                        enabled = excluded.enabled,
                        encrypted_api_key = excluded.encrypted_api_key,
                        key_preview = excluded.key_preview,
                        assist_mode_id = excluded.assist_mode_id,
                        default_model = excluded.default_model,
                        updated_by = excluded.updated_by,
                        updated_at = now()
                    """,
                    (provider_id, api_key, secret, preview, assist_mode_id, args.model, user_id),
                )
            if scopes["entity"]:
                cur.execute(
                    f"""
                    insert into entity_ai_provider_settings
                        (entity_id, provider_type_id, enabled, encrypted_api_key, key_preview, key_policy_id, assist_mode_id, default_model, updated_by, updated_at)
                    values (%s, %s, true, {encrypted_expr}, %s, %s, %s, %s, %s, now())
                    on conflict (entity_id, provider_type_id) do update set
                        enabled = excluded.enabled,
                        encrypted_api_key = excluded.encrypted_api_key,
                        key_preview = excluded.key_preview,
                        key_policy_id = excluded.key_policy_id,
                        assist_mode_id = excluded.assist_mode_id,
                        default_model = excluded.default_model,
                        updated_by = excluded.updated_by,
                        updated_at = now()
                    """,
                    (entity_id, provider_id, api_key, secret, preview, entity_policy_id, assist_mode_id, args.model, user_id),
                )
            if scopes["user"]:
                cur.execute(
                    f"""
                    insert into user_ai_provider_settings
                        (user_id, provider_type_id, enabled, encrypted_api_key, key_preview, key_policy_id, assist_mode_id, default_model, updated_at)
                    values (%s, %s, true, {encrypted_expr}, %s, %s, %s, %s, now())
                    on conflict (user_id, provider_type_id) do update set
                        enabled = excluded.enabled,
                        encrypted_api_key = excluded.encrypted_api_key,
                        key_preview = excluded.key_preview,
                        key_policy_id = excluded.key_policy_id,
                        assist_mode_id = excluded.assist_mode_id,
                        default_model = excluded.default_model,
                        updated_at = now()
                    """,
                    (user_id, provider_id, api_key, secret, preview, user_policy_id, assist_mode_id, args.model),
                )
        conn.commit()

    print("Stored encrypted OpenAI key for: " + ", ".join(scope for scope, enabled in scopes.items() if enabled))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
