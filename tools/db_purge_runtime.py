#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.connection import Database  # noqa: E402
from db.sql import load_query  # noqa: E402


def database_url_from_environment() -> str | None:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        return None

    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    return config.get("DATABASE_URL")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Purge CircuitShelf runtime catalog data while preserving users, "
            "settings, schema migrations, and lookup configuration."
        )
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Run without an interactive confirmation prompt.",
    )
    args = parser.parse_args()

    if not args.yes:
        answer = input(
            "This will delete indexed documents, chunks, images, query logs, "
            "response cache, intelligence, and active sessions. Continue? [y/N] "
        )
        if answer.strip().lower() not in {"y", "yes"}:
            print("Cancelled.")
            return 1

    database_url = database_url_from_environment()
    if not database_url:
        print("DATABASE_URL is required in the environment or config/config.yaml.", file=sys.stderr)
        return 2

    database = Database(database_url)
    with database.connection() as conn:
        conn.execute(load_query("runtime_catalog_reset.sql"))

    print("Runtime catalog purged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
