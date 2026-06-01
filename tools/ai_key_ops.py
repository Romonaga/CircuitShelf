#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
import yaml
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.sql import load_query  # noqa: E402


def load_database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        return ""
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    return str(config.get("DATABASE_URL") or "")


def backup_keys(database_url: str, output_path: Path) -> None:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        rows = conn.execute(load_query("ai_provider_backup_rows.sql")).fetchall()
    payload = {
        "format": "circuitshelf-ai-provider-key-backup-v1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "warning": "Contains encrypted provider keys. Keep with the matching AI_KEY_ENCRYPTION_SECRET.",
        "rows": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    output_path.chmod(0o600)


def restore_keys(database_url: str, input_path: Path) -> int:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("format") != "circuitshelf-ai-provider-key-backup-v1":
        raise ValueError("Unsupported AI provider key backup format.")
    rows = payload.get("rows") or []
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.transaction():
            for row in rows:
                scope = row.get("scope")
                if scope == "system":
                    conn.execute(
                        load_query("ai_provider_system_encrypted_restore.sql"),
                        (
                            bool(row.get("enabled")),
                            row.get("encrypted_api_key") or "",
                            row.get("key_preview") or "",
                            row.get("default_model") or "",
                            row.get("updated_by"),
                            row.get("assist_mode") or "auto",
                            row.get("provider") or "openai",
                        ),
                    )
                elif scope == "entity":
                    conn.execute(
                        load_query("ai_provider_entity_encrypted_restore.sql"),
                        (
                            int(row["scope_id"]),
                            bool(row.get("enabled")),
                            row.get("encrypted_api_key") or "",
                            row.get("key_preview") or "",
                            row.get("default_model") or "",
                            float(row.get("monthly_budget") or 0),
                            int(row.get("warn_percent") or 80),
                            int(row.get("stop_percent") or 100),
                            row.get("updated_by"),
                            row.get("key_policy") or "entity",
                            row.get("assist_mode") or "auto",
                            row.get("provider") or "openai",
                        ),
                    )
                elif scope == "user":
                    conn.execute(
                        load_query("ai_provider_user_encrypted_restore.sql"),
                        (
                            int(row["scope_id"]),
                            bool(row.get("enabled")),
                            row.get("encrypted_api_key") or "",
                            row.get("key_preview") or "",
                            row.get("default_model") or "",
                            float(row.get("monthly_budget") or 0),
                            int(row.get("warn_percent") or 80),
                            int(row.get("stop_percent") or 100),
                            row.get("key_policy") or "user_when_available",
                            row.get("assist_mode") or "auto",
                            row.get("provider") or "openai",
                        ),
                    )
                else:
                    raise ValueError(f"Unsupported provider key scope: {scope}")
    return len(rows)


def rotate_secret(database_url: str, old_secret: str, new_secret: str) -> None:
    if not old_secret or not new_secret:
        raise ValueError("Both old and new encryption secrets are required.")
    if old_secret == new_secret:
        raise ValueError("Old and new encryption secrets are identical.")
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute(load_query("ai_provider_system_secret_rotate.sql"), (old_secret, new_secret))
            conn.execute(load_query("ai_provider_entity_secret_rotate.sql"), (old_secret, new_secret))
            conn.execute(load_query("ai_provider_user_secret_rotate.sql"), (old_secret, new_secret))


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup, restore, or rotate encrypted CircuitShelf AI provider keys.")
    parser.add_argument("--database-url", default=load_database_url())
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup", help="Export encrypted key rows to a JSON backup.")
    backup.add_argument("--output", required=True, type=Path)

    restore = subparsers.add_parser("restore", help="Restore encrypted key rows from a JSON backup.")
    restore.add_argument("--input", required=True, type=Path)

    rotate = subparsers.add_parser("rotate-secret", help="Re-encrypt stored provider keys with a new secret.")
    rotate.add_argument("--old-secret", default=os.environ.get("AI_KEY_ENCRYPTION_SECRET_OLD", ""))
    rotate.add_argument("--new-secret", default=os.environ.get("AI_KEY_ENCRYPTION_SECRET", ""))

    args = parser.parse_args()
    if not args.database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 2

    if args.command == "backup":
        backup_keys(args.database_url, args.output)
        print(f"Wrote encrypted AI key backup to {args.output}")
        return 0
    if args.command == "restore":
        count = restore_keys(args.database_url, args.input)
        print(f"Restored {count} encrypted AI provider settings.")
        return 0
    if args.command == "rotate-secret":
        rotate_secret(args.database_url, args.old_secret, args.new_secret)
        print("Rotated encrypted AI provider keys. Update AI_KEY_ENCRYPTION_SECRET before restarting services.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
