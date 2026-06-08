"""Pull request body rendering shared by installed repo-local helper scripts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _replace_section(template: str, heading: str, lines: list[str]) -> str:
    marker = f"## {heading}"
    start = template.find(marker)
    if start < 0:
        return template.rstrip() + "\n\n" + marker + "\n\n" + "\n".join(lines).rstrip() + "\n"
    body_start = template.find("\n", start)
    if body_start < 0:
        body_start = len(template)
    next_start = template.find("\n## ", body_start + 1)
    replacement = marker + "\n\n" + "\n".join(lines).rstrip() + "\n\n"
    if next_start < 0:
        return template[:start] + replacement
    return template[:start] + replacement + template[next_start + 1 :]


def _task_items(change: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in list(change.get("tasks") or []) if isinstance(item, dict)]


def _change_type_label(change_type: str) -> str | None:
    normalized = str(change_type or "").strip().lower()
    return {
        "feature": "Feature",
        "bugfix": "Bug fix",
        "refactor": "Refactor",
        "documentation": "Documentation / workflow artifact",
        "workflow": "Documentation / workflow artifact",
        "governance": "Documentation / workflow artifact",
        "repo": "Repo organization / cleanup",
        "cleanup": "Repo organization / cleanup",
    }.get(normalized)


def _acceptance_items(change: dict[str, Any]) -> list[str]:
    items: list[str] = []
    for item in list(change.get("acceptance_criteria") or []):
        text = str(item.get("text") or "").strip() if isinstance(item, dict) else str(item or "").strip()
        if text:
            items.append(text)
    return list(dict.fromkeys(items))


def _verification_items(change: dict[str, Any]) -> list[str]:
    items: list[str] = []
    for task in _task_items(change):
        for value in list(task.get("suggested_tests") or []):
            text = str(value or "").strip()
            if text and text not in items:
                items.append(text)
        for evidence in list(task.get("linked_evidence") or []):
            if not isinstance(evidence, dict):
                continue
            label = str(evidence.get("label") or "").strip()
            summary = str(evidence.get("summary") or "").strip()
            kind = str(evidence.get("kind") or "").strip().lower()
            path = str(evidence.get("path") or "").strip()
            if kind == "command" and summary:
                text = f"{label}: {summary}" if label else summary
            else:
                text = f"{label}: {path}" if label and path else label or path
            if text and text not in items:
                items.append(text)
    return items


def _coverage_items(change: dict[str, Any]) -> list[str]:
    tasks = _task_items(change)
    done_count = sum(1 for task in tasks if str(task.get("status") or "").strip() == "done")
    items = [f"{done_count} of {len(tasks)} tracked work items are complete." if tasks else "Tracked workflow tasks were reviewed."]
    for task in tasks:
        title = str(task.get("title") or task.get("task_id") or "").strip()
        logs = [str(item or "").strip() for item in list(task.get("work_log") or []) if str(item or "").strip()]
        if title and logs:
            items.append(f"{title}: {logs[-1]}")
        if len(items) >= 6:
            break
    return items


def _ai_tool_label(ai_disclosure: str) -> str:
    prefix = "AI-assisted - tool(s) used:"
    if ai_disclosure.startswith(prefix):
        return ai_disclosure[len(prefix) :].strip() or "___"
    return "Codex"


def _is_human_authored_only(ai_disclosure: str) -> bool:
    normalized = " ".join(str(ai_disclosure or "").strip().lower().split())
    return normalized in {"human-authored only", "human authored only"} or normalized.startswith("human-authored only:")


def render_pr_body(
    change: dict[str, Any],
    *,
    repo_root: str | Path | None = None,
    template: str,
    no_change_reason: str | None = None,
    linked_change_ids: list[str] | None = None,
) -> str:
    body = template
    workflow = change.get("workflow") if isinstance(change.get("workflow"), dict) else {}
    change_id = str(change.get("change_id") or "").strip()
    change_type = str(change.get("change_type") or "").strip()
    change_type_label = _change_type_label(change_type)
    if change_type_label:
        body = body.replace(f"- [ ] {change_type_label}", f"- [x] {change_type_label}")
    elif change_type:
        body = body.replace("- [ ] Other: ___", f"- [x] Other: {change_type}")

    linked_ids = [str(item or "").strip() for item in list(linked_change_ids or ([change_id] if change_id else [])) if str(item or "").strip()]
    if linked_ids:
        linked = ", ".join(f"`{item}`" for item in linked_ids)
        body = body.replace("- [ ] Linked Verlyn change: `<change-id>`", f"- [x] Linked Verlyn change: {linked}")
    elif no_change_reason:
        body = body.replace("- [ ] No change applies - reason: ___", f"- [x] No change applies - reason: {no_change_reason}")

    acceptance = _acceptance_items(change)
    if acceptance:
        body = _replace_section(body, "Acceptance Criteria", [f"- {item}" for item in acceptance[:12]])

    verification = _verification_items(change)
    if verification:
        lines = [
            "- [ ] Session baseline",
            "- [ ] Architecture check (if configured)",
            f"- [ ] Workstream validation: `python scripts/repo_helpers/workflow/validate.py {change_id or '<id>'} --strict`",
            "- [x] Other:",
            *[f"  - [x] `{item}`" for item in verification[:10]],
        ]
        body = _replace_section(body, "Verification Runs Completed", lines)

    body = _replace_section(body, "Coverage Summary", [f"- {item}" for item in _coverage_items(change)])

    ai_disclosure = str(workflow.get("ai_disclosure") or "").strip()
    owner = str(workflow.get("workflow_owner") or change.get("workflow_owner") or "___").strip() or "___"
    human_only = _is_human_authored_only(ai_disclosure)
    tool_label = _ai_tool_label(ai_disclosure) if ai_disclosure and not human_only else "___"
    extra_ai_lines = [] if ai_disclosure == f"AI-assisted - tool(s) used: {tool_label}" else ["", ai_disclosure] if ai_disclosure and not human_only else []
    body = _replace_section(
        body,
        "AI Assistance Disclosure",
        [
            f"- [x] AI-assisted - tool(s) used: {tool_label or '___'}" if ai_disclosure and not human_only else "- [ ] AI-assisted - tool(s) used: ___",
            f"- [{'x' if human_only else ' '}] Human-authored only",
            "",
            f"Accountable human owner: {owner}",
            *extra_ai_lines,
        ],
    )

    rollback_plan = str(workflow.get("rollback_plan") or change.get("rollback_plan") or "").strip()
    if rollback_plan:
        body = _replace_section(body, "Rollback Plan", [f"- {rollback_plan}"])

    independent_review = str(workflow.get("independent_review") or "").strip().lower()
    if independent_review in {"completed", "complete", "done"}:
        review_lines = [
            "- [ ] Not required for this change - reason: ___",
            "- [x] Completed - reviewer tool: Verlyn workflow gate | findings summary: No blocking findings recorded.",
            "  - Unresolved findings:",
            "    - [ ] ___",
        ]
    else:
        review_lines = [
            "- [x] Not required for this change - reason: Solo workflow or no independent review required by policy.",
            "- [ ] Completed - reviewer tool: ___ | findings summary: ___",
            "  - Unresolved findings:",
            "    - [ ] ___",
        ]
    body = _replace_section(body, "Independent Cross-Agent Review", review_lines)

    open_tasks = [task for task in _task_items(change) if str(task.get("status") or "").strip() not in {"done", "canceled", "archived"}]
    handoff_status = str(workflow.get("handoff_status") or "").strip().lower()
    body = _replace_section(
        body,
        "Handoff Status",
        [
            f"- [{'x' if not open_tasks else ' '}] All acceptance criteria satisfied",
            f"- [{'x' if not open_tasks else ' '}] DB-backed work items updated",
            "- [x] Outstanding blockers or deferred items noted",
            f"- [{'x' if not open_tasks and handoff_status in {'complete', 'completed'} else ' '}] Ready to merge",
        ],
    )
    return body.rstrip() + "\n"


def render_pr_body_for_repo_change(change: dict[str, Any], repo_root: str | Path) -> str:
    template_path = Path(repo_root) / ".github" / "pull_request_template.md"
    template = template_path.read_text(encoding="utf-8")
    return render_pr_body(change, repo_root=repo_root, template=template)
