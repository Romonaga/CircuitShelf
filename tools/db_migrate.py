#!/usr/bin/env python3
"""Apply SQL migrations through psql.

This intentionally uses the local psql client instead of a Python database
driver so the project can track schema versions before choosing its final DB
library.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def migration_version(path: Path) -> int:
    match = re.match(r"^(\d+)_.*\.sql$", path.name)
    if not match:
        raise ValueError(f"Invalid migration filename: {path.name}")
    return int(match.group(1))


def applied_versions(database_url: str, table: str) -> set[int]:
    sql = (
        f"CREATE TABLE IF NOT EXISTS {table} "
        "(version integer PRIMARY KEY, name text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now()); "
        f"SELECT version FROM {table} ORDER BY version;"
    )
    result = subprocess.run(
        ["psql", database_url, "-At", "-c", sql],
        check=True,
        text=True,
        capture_output=True,
    )
    versions = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            versions.add(int(line))
    return versions


def apply_migration(database_url: str, path: Path) -> None:
    subprocess.run(["psql", database_url, "-v", "ON_ERROR_STOP=1", "-f", str(path)], check=True)


def main() -> int:
    config = load_config()
    parser = argparse.ArgumentParser(description="Apply database migrations.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL") or config.get("DATABASE_URL"))
    parser.add_argument("--migrations-dir", default=config.get("DB_MIGRATIONS_DIR", "db/migrations"))
    parser.add_argument("--schema-table", default=config.get("DB_SCHEMA_VERSION_TABLE", "schema_migrations"))
    args = parser.parse_args()

    if not args.database_url:
        print("DATABASE_URL is not set. Add it to the environment or config/config.yaml.", file=sys.stderr)
        return 2

    migrations_dir = PROJECT_ROOT / args.migrations_dir
    migrations = sorted(migrations_dir.glob("*.sql"), key=migration_version)
    applied = applied_versions(args.database_url, args.schema_table)

    pending = [path for path in migrations if migration_version(path) not in applied]
    if not pending:
        print("No pending migrations.")
        return 0

    for path in pending:
        print(f"Applying {path.name}")
        apply_migration(args.database_url, path)

    print(f"Applied {len(pending)} migration(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
