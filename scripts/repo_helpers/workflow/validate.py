#!/usr/bin/env python3
"""Validate DB-backed Verlyn changes from an installed repo."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from _repo_bootstrap import ensure_repo_root_on_path
except ModuleNotFoundError:  # pragma: no cover - package import path
    from scripts.repo_helpers.workflow._repo_bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path(__file__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("item_name", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--help", action="store_true")
    args, _unknown = parser.parse_known_args()
    return args


def _helper(repo_root: Path, *args: str) -> tuple[int, str, str]:
    helper_path = repo_root / "scripts" / "verlyn_workflow.py"
    if not helper_path.exists():
        return 127, "", f"Verlyn helper not found: {helper_path}"
    result = subprocess.run(
        [sys.executable, str(helper_path), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _load_helper_json(repo_root: Path, *args: str) -> tuple[dict[str, Any] | None, str | None]:
    code, stdout, stderr = _helper(repo_root, *args, "--json")
    if code != 0:
        return None, stdout or stderr or f"helper exited with status {code}"
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return None, f"helper returned invalid JSON: {exc}"
    return payload if isinstance(payload, dict) else {}, None


def _change_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    change = payload.get("change")
    if isinstance(change, dict):
        return change
    return payload if isinstance(payload.get("change_id"), str) else {}


def _validate_change_payload(change: dict[str, Any], *, strict: bool) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not change.get("change_id"):
        issues.append({"level": "error", "message": "Change id is missing from DB-backed payload."})
    if not change.get("status"):
        issues.append({"level": "error", "message": "Change status is missing from DB-backed payload."})
    tasks = [item for item in list(change.get("tasks") or []) if isinstance(item, dict)]
    if strict and not tasks:
        issues.append({"level": "error", "message": "Strict validation expected at least one DB-backed work item."})
    if strict and not list(change.get("acceptance_criteria") or []):
        issues.append({"level": "error", "message": "Strict validation expected DB-backed acceptance criteria."})
    return issues


def validate_change(repo_root: Path, change_id: str, strict: bool) -> dict[str, object]:
    payload, error = _load_helper_json(repo_root, "changes", "show", change_id)
    if error:
        return {
            "id": change_id,
            "type": "change",
            "valid": False,
            "issues": [{"level": "error", "message": error}],
        }
    change = _change_from_payload(payload or {})
    issues = _validate_change_payload(change, strict=strict)
    return {
        "id": change_id,
        "type": "change",
        "valid": not any(issue["level"] == "error" for issue in issues),
        "issues": issues,
        "source": "verlyn_db",
        "status": change.get("status"),
        "work_item_count": len([item for item in list(change.get("tasks") or []) if isinstance(item, dict)]),
    }


def list_candidate_changes(repo_root: Path) -> list[str]:
    payload, error = _load_helper_json(repo_root, "changes", "list", "--status-scope", "working", "--detail", "summary")
    if error:
        return []
    candidates = payload.get("changes") or payload.get("items") or []
    if not isinstance(candidates, list):
        candidates = (((payload.get("workspace") or {}) if isinstance(payload.get("workspace"), dict) else {}).get("changes") or [])
    return [
        str(item.get("change_id") or "").strip()
        for item in candidates
        if isinstance(item, dict) and str(item.get("change_id") or "").strip()
    ]


def print_help() -> None:
    print("Usage: python scripts/repo_helpers/workflow/validate.py [change-id] [--strict] [--json]")
    print("       python scripts/repo_helpers/workflow/validate.py --all [--strict] [--json]")
    print("Validates DB-backed Verlyn changes through scripts/verlyn_workflow.py.")


def main() -> int:
    args = parse_args()
    if args.help or (not args.all and not args.item_name):
        print_help()
        return 2 if not args.help else 0
    repo_root = Path.cwd()
    change_ids = list_candidate_changes(repo_root) if args.all else [args.item_name]
    items = [validate_change(repo_root, change_id, args.strict) for change_id in change_ids if change_id]
    passed = sum(1 for item in items if item["valid"])
    failed = len(items) - passed
    if args.json:
        print(json.dumps({"items": items, "summary": {"totals": {"items": len(items), "passed": passed, "failed": failed}}, "version": "2.0", "source": "verlyn_db"}, indent=2))
        return 1 if failed else 0
    for item in items:
        if item["valid"]:
            print(f"PASS: Change '{item['id']}' is valid in Verlyn DB")
        else:
            print(f"FAIL: Change '{item['id']}' is invalid")
            for issue in item["issues"]:
                print(f"- {issue['level'].upper()}: {issue['message']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
