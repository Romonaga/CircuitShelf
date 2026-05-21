#!/usr/bin/env python3
"""Manage CircuitShelf database users."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from db.connection import Database
from db.users import UserStore


CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config.get("DATABASE_URL", "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage CircuitShelf users in Postgres.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("upsert", help="Create or update a user.")
    create.add_argument("username")
    create.add_argument("--password", help="Omit to be prompted without echo.")
    create.add_argument("--admin", action="store_true")
    create.add_argument("--inactive", action="store_true")

    subparsers.add_parser("list", help="List database users.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    database_url = load_database_url()
    if not database_url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2

    store = UserStore(Database(database_url))
    if args.command == "upsert":
        password = args.password or getpass.getpass("Password: ")
        store.upsert_user(
            args.username,
            password,
            is_admin=args.admin,
            is_active=not args.inactive,
        )
        print(f"User '{args.username}' saved.")
        return 0

    if args.command == "list":
        for user in store.list_users():
            admin = "admin" if user["is_admin"] else "user"
            active = "active" if user["is_active"] else "inactive"
            print(f"{user['username']}\t{admin}\t{active}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
