#!/usr/bin/env python3
"""Generate a pre-filled PR body from the repo PR template and change docs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.pr_body import render_pr_body

TEMPLATE_PATH = REPO_ROOT / ".github" / "pull_request_template.md"


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_change(change_id: str) -> dict:
    """Load the live DB-backed change when this script runs inside Verlyn."""

    normalized_change_id = str(change_id or "").strip()
    if not normalized_change_id:
        return {}
    try:
        from analyzer.config_files import load_primary_config_with_overrides
        from platform_data.workstream import get_change_record
    except Exception:
        return {}
    config_path = REPO_ROOT / "analyzer" / "config.yaml"
    try:
        config = load_primary_config_with_overrides(config_path) if config_path.exists() else {}
        change = get_change_record(str(REPO_ROOT), normalized_change_id, config)
    except Exception:
        return {}
    return change if isinstance(change, dict) else {}


def fill_template(template: str, change_ids: list[str], no_change_reason: str | None) -> str:
    change = load_change(change_ids[0]) if len(change_ids) == 1 else {}
    if not change:
        change = {
            "change_id": change_ids[0] if len(change_ids) == 1 else "",
            "change_type": "",
            "tasks": [],
            "workflow": {},
        }
    workflow = change.setdefault("workflow", {})
    if isinstance(workflow, dict):
        workflow.setdefault("workflow_owner", "___")
        workflow.setdefault("ai_disclosure", "AI-assisted - tool(s) used: ___")
    return render_pr_body(
        change,
        repo_root=REPO_ROOT,
        template=template,
        no_change_reason=no_change_reason,
        linked_change_ids=change_ids,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("change_ids", nargs="*")
    parser.add_argument("--no-change-reason")
    args = parser.parse_args()
    if not args.change_ids and not args.no_change_reason:
        print("Provide one or more change ids or --no-change-reason.", file=sys.stderr)
        raise SystemExit(1)
    template = read_file(TEMPLATE_PATH)
    if not template:
        print("PR template not found.", file=sys.stderr)
        raise SystemExit(1)
    print(fill_template(template, args.change_ids, args.no_change_reason))


if __name__ == "__main__":
    main()
