#!/usr/bin/env python3
"""Apply SQL migrations through psql."""

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
QUERY_DIR = PROJECT_ROOT / "db" / "queries"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def migration_version(path: Path) -> int:
    match = re.match(r"^(\d+)_.*\.sql$", path.name)
    if not match:
        raise ValueError(f"Invalid migration filename: {path.name}")
    return int(match.group(1))


def run_query_file(database_url: str, query_name: str, *, capture: bool = False) -> subprocess.CompletedProcess:
    query_path = QUERY_DIR / query_name
    result = subprocess.run(
        ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-At", "-f", str(query_path)],
        check=True,
        text=True,
        capture_output=capture,
    )
    return result


def applied_versions(database_url: str) -> set[int]:
    run_query_file(database_url, "schema_migrations_ensure.sql")
    result = run_query_file(database_url, "schema_migrations_list.sql", capture=True)
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
    args = parser.parse_args()

    if not args.database_url:
        print("DATABASE_URL is not set. Add it to the environment or config/config.yaml.", file=sys.stderr)
        return 2

    migrations_dir = PROJECT_ROOT / args.migrations_dir
    migrations = sorted(migrations_dir.glob("*.sql"), key=migration_version)
    applied = applied_versions(args.database_url)

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
