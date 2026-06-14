#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.ai_cost_reconciliation import (  # noqa: E402
    OpenAIOrganizationUsageClient,
    reconcile_cost_bucket,
    verified_cost_from_openai_payload,
)
from db.ai_provider_store import AIProviderStore  # noqa: E402
from db.connection import Database  # noqa: E402


def parse_datetime(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise argparse.ArgumentTypeError("date/time value is required")
    try:
        if len(raw) == 10:
            return datetime.combine(date.fromisoformat(raw), time.min, tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date/time: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_config() -> dict:
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def unix_seconds(value: datetime) -> int:
    return int(value.timestamp())


def main() -> int:
    config = load_config()
    parser = argparse.ArgumentParser(description="Reconcile recorded OpenAI assist estimates to OpenAI organization costs.")
    parser.add_argument("--start", required=True, type=parse_datetime, help="Inclusive UTC start date/time, e.g. 2026-06-01.")
    parser.add_argument("--end", required=True, type=parse_datetime, help="Exclusive UTC end date/time, e.g. 2026-06-14.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL") or config.get("DATABASE_URL"))
    parser.add_argument("--admin-key", default=os.environ.get("OPENAI_ADMIN_KEY"), help="OpenAI Admin API key. Prefer OPENAI_ADMIN_KEY.")
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--bucket-width", default="1d", choices=["1d"])
    parser.add_argument("--group-by", action="append", choices=["project_id", "line_item", "api_key_id"], default=[])
    parser.add_argument("--project-id", action="append", default=[])
    parser.add_argument("--api-key-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true", help="Fetch and calculate but do not persist final costs.")
    args = parser.parse_args()

    if args.end <= args.start:
        print("--end must be after --start", file=sys.stderr)
        return 2
    if not args.database_url:
        print("DATABASE_URL is not set. Add it to the environment or config/config.yaml.", file=sys.stderr)
        return 2
    database = Database(args.database_url)
    store = AIProviderStore(database=database, config_path=PROJECT_ROOT / "config" / "config.yaml")
    admin_key = args.admin_key or store.admin_api_key_for_provider("openai")
    if not admin_key:
        print(
            "OpenAI organization cost backfill needs an admin key. Configure the system OpenAI organization cost key or set OPENAI_ADMIN_KEY.",
            file=sys.stderr,
        )
        database.close()
        return 2
    client = OpenAIOrganizationUsageClient(admin_api_key=admin_key, base_url=args.base_url)
    allocation_method = "estimated_cost_proportional"

    run_id = ""
    if not args.dry_run:
        run_id = store.create_cost_reconciliation_run(
            provider="openai",
            source="openai_organization_costs",
            start_time=args.start,
            end_time=args.end,
            bucket_width=args.bucket_width,
            allocation_method=allocation_method,
        )
    try:
        payload = client.fetch_costs(
            start_time=unix_seconds(args.start),
            end_time=unix_seconds(args.end),
            bucket_width=args.bucket_width,
            group_by=args.group_by,
            project_ids=args.project_id,
            api_key_ids=args.api_key_id,
        )
        verified_cost = verified_cost_from_openai_payload(payload)
        events = store.list_openai_events_for_reconciliation(start_time=args.start, end_time=args.end)
        effective_run_id = run_id or "dry-run"
        updates = reconcile_cost_bucket(events, verified_cost_usd=verified_cost, reconciliation_run_id=effective_run_id)
        estimated_cost = sum((update.estimated_cost_usd for update in updates), Decimal("0"))

        if not args.dry_run:
            store.apply_cost_reconciliation_updates(updates)
            store.complete_cost_reconciliation_run(
                run_id=run_id,
                verified_cost=verified_cost,
                estimated_cost=estimated_cost,
                event_count=len(updates),
                raw_provider_payload=payload,
            )

        print(f"OpenAI reconciliation {'dry run' if args.dry_run else 'complete'}")
        print(f"Window: {args.start.isoformat()} to {args.end.isoformat()}")
        print(f"Verified cost: ${verified_cost:.8f}")
        print(f"Estimated event cost: ${estimated_cost:.8f}")
        print(f"Events reconciled: {len(updates)}")
        if run_id:
            print(f"Run ID: {run_id}")
        return 0
    except Exception as exc:
        if run_id:
            store.fail_cost_reconciliation_run(run_id=run_id, error_message=str(exc))
        raise
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
