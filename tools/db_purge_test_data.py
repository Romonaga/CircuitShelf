#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import psycopg
import yaml
from psycopg import sql
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


RUNTIME_TABLES = [
    "assembly_learning_sessions",
    "assembly_photo_checks",
    "assembly_plan_notes",
    "assembly_plan_parts",
    "assembly_plan_power_notes",
    "assembly_plan_sources",
    "assembly_plan_steps",
    "assembly_plans",
    "conversation_turns",
    "conversations",
    "response_cache_chat_turns",
    "response_cache_sources",
    "response_cache_entries",
    "query_log_sources",
    "query_logs",
    "ai_assist_events",
    "performance_resource_samples",
    "performance_work_runs",
    "local_gpu_work_items",
    "ingest_jobs",
    "ingest_run_documents",
    "ingest_runs",
    "ingest_runtime_status",
    "document_ingest_ai_reviews",
    "document_ingest_scope_overrides",
    "document_scope_audit",
    "document_intelligence_facts",
    "document_intelligence_pins",
    "document_intelligence",
    "chunk_quality_flags",
    "document_images",
    "document_chunks",
    "document_pages",
    "documents",
]

OPTIONAL_SESSION_TABLES = [
    "user_sessions",
]

PRESERVED_CATEGORIES = [
    "users and sessions by default",
    "entities, memberships, and roles",
    "password policies",
    "user preferences",
    "system/entity/user AI provider settings and encrypted keys",
    "AI model pricing and pricing overrides",
    "lookup/config tables",
    "lab inventory and aliases",
    "schema migrations",
]

PURGE_SCOPE = [
    "runtime database rows: documents, chunks, images, ingest runs, conversations, cache, AI usage, and performance samples",
    "training upload folder contents",
]


def database_url_from_environment() -> str | None:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        return None

    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    return config.get("DATABASE_URL")


def training_dir_from_config() -> Path:
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        return PROJECT_ROOT / "training"

    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    configured = config.get("TRAINING_DIR") or "training"
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def existing_tables(conn: psycopg.Connection, table_names: list[str]) -> list[str]:
    rows = conn.execute(
        """
        select tablename
          from pg_tables
         where schemaname = 'public'
           and tablename = any(%s)
         order by array_position(%s, tablename)
        """,
        (table_names, table_names),
    ).fetchall()
    return [str(row["tablename"]) for row in rows]


def table_counts(conn: psycopg.Connection, table_names: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in table_names:
        query = sql.SQL("select count(*) as row_count from {}").format(sql.Identifier(table))
        counts[table] = int(conn.execute(query).fetchone()["row_count"])
    return counts


def truncate_tables(conn: psycopg.Connection, table_names: list[str]) -> None:
    if not table_names:
        return
    query = sql.SQL("truncate table {} restart identity").format(
        sql.SQL(", ").join(sql.Identifier(table) for table in table_names)
    )
    conn.execute(query)


def reset_ingest_runtime_status(conn: psycopg.Connection) -> None:
    if "ingest_runtime_status" not in existing_tables(conn, ["ingest_runtime_status"]):
        return
    status = {
        "enabled": True,
        "running": False,
        "stage": "idle",
        "currentFiles": [],
        "processedFiles": 0,
        "totalFiles": 0,
        "lastStartedAt": None,
        "lastFinishedAt": None,
        "lastReason": None,
        "lastResult": "purged",
        "lastError": None,
        "lastChanges": {
            "added": 0,
            "modified": 0,
            "removed": 0,
            "unchanged": 0,
            "addedFiles": [],
            "modifiedFiles": [],
            "removedFiles": [],
        },
        "nextCheckAt": None,
        "details": {},
    }
    conn.execute(
        """
        insert into ingest_runtime_status (id, status, updated_at)
        values (1, %s::jsonb, now())
        on conflict (id) do update
        set status = excluded.status,
            updated_at = now()
        """,
        (json.dumps(status),),
    )


def assert_safe_training_dir(training_dir: Path) -> Path:
    resolved = training_dir.resolve()
    project_root = PROJECT_ROOT.resolve()
    if resolved == project_root:
        raise RuntimeError("Refusing to purge the project root as a training directory.")
    if project_root not in resolved.parents:
        raise RuntimeError(f"Refusing to purge training directory outside the project: {resolved}")
    return resolved


def purge_training_dir(training_dir: Path, *, dry_run: bool) -> tuple[int, int]:
    resolved = assert_safe_training_dir(training_dir)
    if not resolved.exists():
        return 0, 0

    files = 0
    dirs = 0
    for child in resolved.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            dirs += 1
            if not dry_run:
                shutil.rmtree(child)
        else:
            files += 1
            if not dry_run:
                child.unlink()
    return files, dirs


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Purge CircuitShelf dogfooding data and the training upload folder while "
            "preserving accounts, entities, settings, AI keys/config, pricing, lookup "
            "tables, and inventory."
        )
    )
    parser.add_argument("--yes", action="store_true", help="Run without an interactive confirmation prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be purged without deleting anything.")
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="Only purge database runtime tables. Do not use for normal dogfood resets because it leaves training uploads in place.",
    )
    parser.add_argument("--training-only", action="store_true", help="Only purge the training upload folder.")
    parser.add_argument(
        "--clear-sessions",
        action="store_true",
        help="Also clear user sessions. By default active logins are preserved.",
    )
    args = parser.parse_args()

    if args.db_only and args.training_only:
        print("--db-only and --training-only cannot be used together.", file=sys.stderr)
        return 2

    if not args.yes and not args.dry_run:
        print("This will clear CircuitShelf dogfooding/runtime data.")
        print("Purged by default:")
        for item in PURGE_SCOPE:
            print(f"  - {item}")
        print("Preserved:")
        for category in PRESERVED_CATEGORIES:
            print(f"  - {category}")
        answer = input("Continue? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Cancelled.")
            return 1

    database_url = database_url_from_environment()
    training_dir = training_dir_from_config()

    if not args.training_only and not database_url:
        print("DATABASE_URL is required in the environment or config/config.yaml.", file=sys.stderr)
        return 2

    if not args.training_only:
        requested_tables = RUNTIME_TABLES + (OPTIONAL_SESSION_TABLES if args.clear_sessions else [])
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            tables = existing_tables(conn, requested_tables)
            counts = table_counts(conn, tables)
            nonempty = {table: count for table, count in counts.items() if count}
            if args.dry_run:
                print("Database tables that would be truncated:")
                for table in tables:
                    print(f"  {table}: {counts[table]} rows")
            else:
                truncate_tables(conn, tables)
                reset_ingest_runtime_status(conn)
                conn.commit()
                print(f"Purged {sum(nonempty.values())} rows from {len(tables)} database tables.")

    if not args.db_only:
        files, dirs = purge_training_dir(training_dir, dry_run=args.dry_run)
        action = "Would purge" if args.dry_run else "Purged"
        print(f"{action} training folder {training_dir}: {files} files, {dirs} directories.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
