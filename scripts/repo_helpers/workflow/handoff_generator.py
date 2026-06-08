#!/usr/bin/env python3
"""Generate a paste-ready review handoff for a DB-backed Verlyn change."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

try:
    from _repo_bootstrap import ensure_repo_root_on_path
except ModuleNotFoundError:  # pragma: no cover - package import path
    from scripts.repo_helpers.workflow._repo_bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path(__file__)


def try_exec(args: list[str], repo_root: Path) -> str | None:
    try:
        return subprocess.run(args, cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def git_scoped_output(repo_root: Path, subcommand: str, scope_paths: list[str] | None) -> str | None:
    commands = [
        ["git", "diff", subcommand, "origin/main...HEAD"],
        ["git", "diff", subcommand, "HEAD~5..HEAD"],
        ["git", "diff", subcommand],
    ]
    for command in commands:
        scoped = list(command)
        if scope_paths:
            scoped.extend(["--", *scope_paths])
        result = try_exec(scoped, repo_root)
        if result is not None:
            return result
    return None


def load_change(repo_root: Path, change_id: str) -> tuple[dict[str, Any], str | None]:
    helper_path = repo_root / "scripts" / "verlyn_workflow.py"
    if not helper_path.exists():
        return {}, f"Verlyn helper not found: {helper_path}"
    result = subprocess.run(
        [sys.executable, str(helper_path), "changes", "show", change_id, "--json"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}, result.stdout.strip() or result.stderr.strip() or f"helper exited with status {result.returncode}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {}, f"helper returned invalid JSON: {exc}"
    change = payload.get("change") if isinstance(payload, dict) else None
    return change if isinstance(change, dict) else {}, None


def _proposal_sections(change: dict[str, Any]) -> dict[str, str]:
    sections = change.get("proposal_sections")
    return sections if isinstance(sections, dict) else {}


def _open_acceptance(change: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for task in list(change.get("tasks") or []):
        if not isinstance(task, dict):
            continue
        if str(task.get("status") or "").strip().lower() in {"done", "canceled", "archived"}:
            continue
        title = str(task.get("title") or task.get("task_id") or "work item").strip()
        for item in list(task.get("acceptance_criteria") or []):
            text = str(item or "").strip()
            if text:
                out.append(f"- {title}: {text}")
    return out


def main() -> int:
    repo_root = Path.cwd()
    change_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not change_id:
        print("Usage: python scripts/repo_helpers/workflow/handoff_generator.py <change-id>", file=sys.stderr)
        return 1
    change, error = load_change(repo_root, change_id)
    if error:
        print(error, file=sys.stderr)
        return 1
    sections = _proposal_sections(change)
    proposal_summary = str(sections.get("summary") or change.get("description") or "(not recorded)").strip()
    proposal_scope = str(sections.get("scope") or "(not recorded)").strip()
    open_acceptance = _open_acceptance(change) or ["- Review the DB-backed Verlyn work items for current acceptance status."]
    diff_stat = git_scoped_output(repo_root, "--stat", None) or "(git diff unavailable)"
    print(f"""========================================================================
  CROSS-AGENT REVIEW HANDOFF
  Change:    {change_id}
  Generated: {date.today().isoformat()}
========================================================================

CHANGE SUMMARY
{proposal_summary}

Scope:
{proposal_scope}

FILES CHANGED
{diff_stat}

OPEN ACCEPTANCE CRITERIA
{chr(10).join(open_acceptance)}

Review independently. Record findings with explicit dispositions:
fixed | accepted risk | deferred | not reproducible
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
