#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg
import yaml
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        return str(config.get("DATABASE_URL") or "")
    return ""


def pg_restore_table(dump_path: Path, table: str) -> str:
    result = subprocess.run(
        ["pg_restore", "-a", "-f", "-", "-t", table, str(dump_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def parse_copy_table(sql_text: str, table: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    columns: list[str] = []
    in_copy = False
    prefix = f"COPY public.{table} ("
    for line in sql_text.splitlines():
        if line.startswith(prefix):
            raw_columns = line[len(prefix):].split(") FROM stdin;", 1)[0]
            columns = [column.strip() for column in raw_columns.split(",")]
            in_copy = True
            continue
        if in_copy and line == r"\.":
            break
        if in_copy:
            values = parse_copy_line(line)
            rows.append(dict(zip(columns, values, strict=False)))
    return rows


def parse_copy_line(line: str) -> list[Any]:
    values = line.split("\t")
    return [None if value == r"\N" else unescape_copy_value(value) for value in values]


def unescape_copy_value(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\" or index == len(value) - 1:
            result.append(char)
            index += 1
            continue
        marker = value[index + 1]
        if marker == "n":
            result.append("\n")
        elif marker == "r":
            result.append("\r")
        elif marker == "t":
            result.append("\t")
        elif marker == "b":
            result.append("\b")
        elif marker == "f":
            result.append("\f")
        elif marker == "v":
            result.append("\v")
        else:
            result.append(marker)
        index += 2
    return "".join(result)


def recover_inventory(database_url: str, dump_path: Path, *, dry_run: bool) -> dict[str, int]:
    backup_users = parse_copy_table(pg_restore_table(dump_path, "users"), "users")
    backup_parts = parse_copy_table(pg_restore_table(dump_path, "lab_parts"), "lab_parts")
    backup_aliases = parse_copy_table(pg_restore_table(dump_path, "lab_part_aliases"), "lab_part_aliases")
    backup_usernames_by_id = {str(row["id"]): row["username"] for row in backup_users if row.get("id") and row.get("username")}

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        current_users = {
            row["username"]: int(row["id"])
            for row in conn.execute("SELECT id, username FROM users").fetchall()
        }
        old_to_new_user_id = {
            old_id: current_users[username]
            for old_id, username in backup_usernames_by_id.items()
            if username in current_users
        }
        restorable_parts = [part for part in backup_parts if str(part.get("user_id")) in old_to_new_user_id]
        restorable_part_ids = {part["id"] for part in restorable_parts}
        restorable_aliases = [alias for alias in backup_aliases if alias.get("part_id") in restorable_part_ids]

        if dry_run:
            return {
                "backupUsers": len(backup_users),
                "mappedUsers": len(old_to_new_user_id),
                "backupParts": len(backup_parts),
                "restorableParts": len(restorable_parts),
                "backupAliases": len(backup_aliases),
                "restorableAliases": len(restorable_aliases),
                "insertedParts": 0,
                "insertedAliases": 0,
            }

        inserted_parts = 0
        inserted_aliases = 0
        old_to_actual_part_id: dict[str, str] = {}
        with conn.transaction():
            for part in restorable_parts:
                old_part_id = str(part["id"])
                new_user_id = old_to_new_user_id[str(part["user_id"])]
                row = conn.execute(
                    """
                    INSERT INTO lab_parts (
                        id, user_id, display_name, normalized_name, part_type,
                        quantity, location, notes, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, normalized_name) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        part_type = EXCLUDED.part_type,
                        quantity = EXCLUDED.quantity,
                        location = EXCLUDED.location,
                        notes = EXCLUDED.notes,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id
                    """,
                    (
                        old_part_id,
                        new_user_id,
                        part.get("display_name") or "",
                        part.get("normalized_name") or "",
                        part.get("part_type") or "component",
                        int(part.get("quantity") or 0),
                        part.get("location") or "",
                        part.get("notes") or "",
                        part.get("created_at"),
                        part.get("updated_at"),
                    ),
                ).fetchone()
                old_to_actual_part_id[old_part_id] = str(row["id"])
                inserted_parts += 1

            if old_to_actual_part_id:
                conn.execute(
                    "DELETE FROM lab_part_aliases WHERE part_id = ANY(%s)",
                    (list(old_to_actual_part_id.values()),),
                )

            for alias in restorable_aliases:
                part_id = old_to_actual_part_id.get(str(alias["part_id"]))
                if not part_id:
                    continue
                conn.execute(
                    """
                    INSERT INTO lab_part_aliases (part_id, alias, normalized_alias, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (part_id, normalized_alias) DO NOTHING
                    """,
                    (
                        part_id,
                        alias.get("alias") or "",
                        alias.get("normalized_alias") or "",
                        alias.get("created_at"),
                    ),
                )
                inserted_aliases += 1

            conn.execute(
                "SELECT setval(pg_get_serial_sequence('lab_part_aliases', 'id'), coalesce((SELECT max(id) FROM lab_part_aliases), 1), true)"
            )

    return {
        "backupUsers": len(backup_users),
        "mappedUsers": len(old_to_new_user_id),
        "backupParts": len(backup_parts),
        "restorableParts": len(restorable_parts),
        "backupAliases": len(backup_aliases),
        "restorableAliases": len(restorable_aliases),
        "insertedParts": inserted_parts,
        "insertedAliases": inserted_aliases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover CircuitShelf lab inventory from a pg_dump custom backup.")
    parser.add_argument("dump", type=Path)
    parser.add_argument("--database-url", default=load_database_url())
    parser.add_argument("--apply", action="store_true", help="Write recovered inventory rows to the current database.")
    args = parser.parse_args()

    if not args.database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 2
    if not args.dump.exists():
        print(f"Dump not found: {args.dump}", file=sys.stderr)
        return 2

    result = recover_inventory(args.database_url, args.dump, dry_run=not args.apply)
    mode = "applied" if args.apply else "dry-run"
    print(f"Inventory recovery {mode}:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
