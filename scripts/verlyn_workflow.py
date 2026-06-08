#!/usr/bin/env python3
"""Repo-local mode wrapper for Verlyn workflow commands."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _bootstrap_repo_python() -> None:
    """Prefer the repo virtualenv before importing Verlyn runtime modules."""
    if os.environ.get("VERLYN_HELPER_SKIP_VENV_REEXEC") == "1":
        return
    venv_python = REPO_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not venv_python.exists():
        return
    try:
        venv_root = (REPO_ROOT / ".venv").resolve()
        current_prefix = Path(sys.prefix).resolve()
        current_python = Path(sys.executable).absolute()
        target_python = venv_python.absolute()
    except Exception:
        venv_root = REPO_ROOT / ".venv"
        current_prefix = Path(sys.prefix)
        current_python = Path(sys.executable)
        target_python = venv_python
    if current_prefix == venv_root or current_python == target_python:
        return
    os.execv(str(venv_python), [str(venv_python), *sys.argv])


_bootstrap_repo_python()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml

WORKFLOW_PACK_METADATA_PATH = REPO_ROOT / ".verlyn" / "workflow_pack.json"
ASSISTANT_ROUTE_PATH = REPO_ROOT / ".verlyn" / "assistant_route.json"
ASSISTANT_GOVERNANCE_RELOAD_PATH = REPO_ROOT / ".verlyn" / "assistant_governance_reload.json"
SANITIZED_VERLYN_ENV_KEYS = (
    "VERLYN_BIN",
    "VERLYN_HOME",
    "VERLYN_CONFIG",
    "VERLYN_WORKSPACE_ROOT",
)
TERMINAL_CHANGE_ROUTE_STATUSES = {"merged", "archived"}
PLANNING_ONLY_CHANGE_ROUTE_STATUSES = {"draft"}
NON_EDITABLE_CHANGE_STATUSES = TERMINAL_CHANGE_ROUTE_STATUSES | PLANNING_ONLY_CHANGE_ROUTE_STATUSES | {"deferred"}
_DB_CHANGE_PAYLOADS_CACHE: list[dict[str, object]] | None = None
_DB_CHANGE_PAYLOAD_MAP_CACHE: dict[str, dict[str, object]] | None = None
_CHANGE_RECORD_PAYLOAD_CACHE: dict[str, dict[str, object] | None] = {}
_REPO_CONFIG_CACHE: dict[str, object] | None = None
GOVERNANCE_RECEIPT_SCHEMA_FAMILY = "assistant_governance_reload"
GOVERNANCE_RECEIPT_SCHEMA_VERSION = 1
GOVERNANCE_CONTRACT_FILE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("system_governance", "AGENTS.md", "Verlyn system governance and precedence"),
    ("project_rules", "RULES.md", "Editable project guidance layer"),
    ("runtime_context", ".verlyn/runtime_context.json", "Compact recovery summary for assistants"),
    ("ai_usage_policy", "Documentation/AI_USAGE_POLICY.md", "AI usage policy for Verlyn work"),
    ("assistant_startup", "Documentation/guides/VERLYN_ASSISTANT_STARTUP.md", "Assistant startup and Verlyn usage guide"),
)
ASSISTANT_STARTUP_COMMANDS: tuple[tuple[str, str], ...] = (
    (".venv/bin/python scripts/verlyn_workflow.py assistant-startup --json", "Reload the governed startup contract and record a visible receipt."),
    (".venv/bin/python scripts/verlyn_workflow.py context --json", "Inspect repo/workspace state plus editing-route and governance-reload verdicts."),
    (".venv/bin/python scripts/verlyn_workflow.py assert-edit-route --json", "Fail closed before editing when either the route or governance reload is blocked."),
    (".venv/bin/python scripts/verlyn_workflow.py status", "See the current routed change and work-item backlog."),
    (".venv/bin/python scripts/verlyn_workflow.py inbox", "See work that is ready, blocked, or waiting for review."),
)


def _clear_change_payload_caches() -> None:
    global _DB_CHANGE_PAYLOADS_CACHE, _DB_CHANGE_PAYLOAD_MAP_CACHE
    _DB_CHANGE_PAYLOADS_CACHE = None
    _DB_CHANGE_PAYLOAD_MAP_CACHE = None
    _CHANGE_RECORD_PAYLOAD_CACHE.clear()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative_repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except Exception:
        return path.as_posix()


def _operator_notice(status: str, *, receipt_path: str) -> str:
    if status == "verified":
        return (
            "Governance was reloaded for this session. Required repo rules were reread, "
            f"and the visible receipt is recorded at {receipt_path}."
        )
    if status == "blocked_stale_governance_reload":
        return (
            "Governance reload is stale because one or more governed files changed. "
            "Rerun assistant startup before work continues."
        )
    return (
        "Governance reload has not run for this session yet. "
        "Run assistant startup before work continues."
    )


def _load_runtime_context_document() -> dict[str, object]:
    runtime_context_path = REPO_ROOT / ".verlyn" / "runtime_context.json"
    if not runtime_context_path.exists() or not runtime_context_path.is_file():
        return {}
    try:
        payload = json.loads(runtime_context_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _governance_contract_snapshot() -> dict[str, object]:
    runtime_context = _load_runtime_context_document()
    startup_read_order = [
        str(item).strip()
        for item in list(runtime_context.get("startup_read_order") or [])
        if str(item).strip()
    ]
    files: list[dict[str, object]] = []
    digest = hashlib.sha256()
    for role, relative_path, summary in GOVERNANCE_CONTRACT_FILE_SPECS:
        path = (REPO_ROOT / relative_path).resolve()
        exists = path.exists() and path.is_file()
        if exists:
            content = path.read_text(encoding="utf-8")
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        else:
            content_hash = None
            modified_at = None
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update((content_hash or "missing").encode("utf-8"))
        digest.update(b"\0")
        files.append(
            {
                "role": role,
                "path": relative_path,
                "summary": summary,
                "exists": exists,
                "content_hash": content_hash,
                "modified_at": modified_at,
            }
        )
    return {
        "schema_family": GOVERNANCE_RECEIPT_SCHEMA_FAMILY,
        "schema_version": GOVERNANCE_RECEIPT_SCHEMA_VERSION,
        "repo_root": str(REPO_ROOT),
        "contract_hash": digest.hexdigest(),
        "startup_read_order": startup_read_order,
        "files": files,
    }


def _save_governance_reload_state(payload: dict[str, object]) -> None:
    ASSISTANT_GOVERNANCE_RELOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    ASSISTANT_GOVERNANCE_RELOAD_PATH.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def _load_governance_reload_state() -> dict[str, object] | None:
    if not ASSISTANT_GOVERNANCE_RELOAD_PATH.exists() or not ASSISTANT_GOVERNANCE_RELOAD_PATH.is_file():
        return None
    try:
        payload = json.loads(ASSISTANT_GOVERNANCE_RELOAD_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("schema_family") or "").strip() != GOVERNANCE_RECEIPT_SCHEMA_FAMILY:
        return None
    return payload


def _record_governance_reload(*, source: str) -> dict[str, object]:
    snapshot = _governance_contract_snapshot()
    payload = {
        **snapshot,
        "recorded_at": _now_iso(),
        "source": source,
        "summary": "Recorded the assistant governance reload receipt for the required Verlyn contract files.",
    }
    _save_governance_reload_state(payload)
    return payload


def _assistant_startup_payload(*, source: str) -> dict[str, object]:
    receipt = _record_governance_reload(source=source)
    workflow_api = [
        {"command": command, "purpose": purpose}
        for command, purpose in ASSISTANT_STARTUP_COMMANDS
    ]
    return {
        "product": "Verlyn",
        "startup_read_order": list(receipt.get("startup_read_order") or []),
        "governance_reload": _governance_reload_gate_payload(),
        "governance_files": list(receipt.get("files") or []),
        "workflow_api": workflow_api,
        "startup_steps": [
            "Reread the governed contract files before making workflow decisions.",
            "Use repo-local helper and API paths instead of reconstructing workflow state from memory.",
            "Treat the recorded governance receipt as the visible proof that startup was reloaded for this session.",
        ],
    }


def _governance_reload_gate_payload() -> dict[str, object]:
    current_snapshot = _governance_contract_snapshot()
    recorded = _load_governance_reload_state()
    required_paths = [item["path"] for item in list(current_snapshot.get("files") or []) if isinstance(item, dict)]
    relative_receipt_path = _relative_repo_path(ASSISTANT_GOVERNANCE_RELOAD_PATH)
    if not recorded:
        return {
            "status": "blocked_missing_governance_reload",
            "allowed": False,
            "summary": "The assistant governance contract has not been reloaded for this repo-local session yet.",
            "next_step": "Run `python scripts/verlyn_workflow.py assistant-startup --json` before continuing.",
            "operator_notice": _operator_notice("blocked_missing_governance_reload", receipt_path=relative_receipt_path),
            "required_paths": required_paths,
            "startup_read_order": current_snapshot.get("startup_read_order") or [],
            "recorded_at": None,
            "source": None,
            "contract_hash": current_snapshot.get("contract_hash"),
            "receipt_path": relative_receipt_path,
        }
    recorded_hash = str(recorded.get("contract_hash") or "").strip()
    current_hash = str(current_snapshot.get("contract_hash") or "").strip()
    if recorded_hash != current_hash:
        current_files = {
            str(item.get("path") or "").strip(): str(item.get("content_hash") or "").strip() or None
            for item in list(current_snapshot.get("files") or [])
            if isinstance(item, dict)
        }
        recorded_files = {
            str(item.get("path") or "").strip(): str(item.get("content_hash") or "").strip() or None
            for item in list(recorded.get("files") or [])
            if isinstance(item, dict)
        }
        changed_paths = sorted(path for path, digest in current_files.items() if recorded_files.get(path) != digest)
        return {
            "status": "blocked_stale_governance_reload",
            "allowed": False,
            "summary": "The recorded assistant governance reload receipt is stale because the governed contract files changed.",
            "next_step": "Run `python scripts/verlyn_workflow.py assistant-startup --json` again before continuing.",
            "operator_notice": _operator_notice("blocked_stale_governance_reload", receipt_path=relative_receipt_path),
            "required_paths": required_paths,
            "changed_paths": changed_paths,
            "startup_read_order": current_snapshot.get("startup_read_order") or [],
            "recorded_at": str(recorded.get("recorded_at") or "").strip() or None,
            "source": str(recorded.get("source") or "").strip() or None,
            "contract_hash": current_hash,
            "receipt_path": relative_receipt_path,
        }
    return {
        "status": "verified",
        "allowed": True,
        "summary": "Assistant governance reload is verified for the current repo contract.",
        "next_step": None,
        "operator_notice": _operator_notice("verified", receipt_path=relative_receipt_path),
        "required_paths": required_paths,
        "startup_read_order": current_snapshot.get("startup_read_order") or [],
        "recorded_at": str(recorded.get("recorded_at") or "").strip() or None,
        "source": str(recorded.get("source") or "").strip() or None,
        "contract_hash": current_hash,
        "receipt_path": relative_receipt_path,
    }


def _installed_verlyn_home() -> Path | None:
    payload = _workflow_pack_metadata()
    if payload is None:
        return None
    configured_home = str(payload.get("verlyn_home") or "").strip()
    if not configured_home:
        return None
    home_root = Path(configured_home).expanduser().resolve()
    cli_path = home_root / "cli.py"
    if not cli_path.exists():
        return None
    return home_root


def _installed_verlyn_executable() -> Path | None:
    payload = _workflow_pack_metadata()
    if payload is None:
        return None
    for key in ("verlyn_executable", "verlyn_bin"):
        configured_path = str(payload.get(key) or "").strip()
        if not configured_path:
            continue
        candidate = Path(configured_path).expanduser().resolve()
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _workflow_pack_metadata() -> dict[str, object] | None:
    if not WORKFLOW_PACK_METADATA_PATH.exists() or not WORKFLOW_PACK_METADATA_PATH.is_file():
        return None
    try:
        payload = json.loads(WORKFLOW_PACK_METADATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _configured_workspace_root() -> str | None:
    payload = _workflow_pack_metadata()
    if not isinstance(payload, dict):
        return None
    workspace_root = str(payload.get("workspace_root") or "").strip()
    if not workspace_root:
        return None
    return str(Path(workspace_root).expanduser().resolve())


def _repo_config() -> dict[str, object]:
    global _REPO_CONFIG_CACHE
    if _REPO_CONFIG_CACHE is not None:
        return dict(_REPO_CONFIG_CACHE)
    config_paths: list[Path] = []
    for key in ("VERLYN_CONFIG", "VERLYN_CONFIG_PATH"):
        configured = str(os.environ.get(key) or "").strip()
        if configured:
            config_paths.append(Path(configured).expanduser().resolve())
    installed_home = _installed_verlyn_home()
    if installed_home is not None and installed_home != REPO_ROOT:
        config_paths.append(installed_home / "analyzer" / "config.yaml")
    config_paths.append(REPO_ROOT / "analyzer" / "config.yaml")
    for config_path in config_paths:
        if not config_path.exists():
            continue
        try:
            from cli import load_config

            payload = load_config(str(config_path))
        except Exception:
            try:
                payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
        _REPO_CONFIG_CACHE = payload if isinstance(payload, dict) else {}
        return dict(_REPO_CONFIG_CACHE)
    _REPO_CONFIG_CACHE = {}
    return dict(_REPO_CONFIG_CACHE)


def _verlyn_command() -> list[str] | None:
    local_cli = REPO_ROOT / "cli.py"
    local_python = REPO_ROOT / ".venv" / "bin" / "python"
    if local_cli.exists():
        return [str(local_python if local_python.exists() else Path(sys.executable).resolve()), "-B", str(local_cli)]

    installed_executable = _installed_verlyn_executable()
    if installed_executable is not None:
        return [str(installed_executable)]

    installed_home = _installed_verlyn_home()
    if installed_home is not None:
        cli_path = installed_home / "cli.py"
        home_python = installed_home / ".venv" / "bin" / "python"
        return [str(home_python if home_python.exists() else Path(sys.executable).resolve()), "-B", str(cli_path)]

    verlyn_bin = shutil.which("verlyn")
    if verlyn_bin:
        return [verlyn_bin]

    return None


def _sanitized_verlyn_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in SANITIZED_VERLYN_ENV_KEYS:
        env.pop(key, None)
    return env


def _run(
    command: list[str],
    *,
    emit_output: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = _sanitized_verlyn_env()
    configured_workspace_root = _configured_workspace_root()
    if configured_workspace_root:
        env["VERLYN_WORKSPACE_ROOT"] = configured_workspace_root
    if not capture_output:
        return subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=None if emit_output else subprocess.DEVNULL,
            stderr=None if emit_output else subprocess.DEVNULL,
            text=True,
        )
    result = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if emit_output and result.stdout:
        sys.stdout.write(result.stdout)
    if emit_output and result.stderr:
        sys.stderr.write(result.stderr)
    return result


def _load_service_mode() -> dict[str, object]:
    try:
        from server.runtime_settings import load_service_mode

        service_mode = load_service_mode(_configured_workspace_root() or REPO_ROOT, _repo_config())
    except Exception:
        return {"enabled": False, "reason": "", "message": ""}
    if not isinstance(service_mode, dict):
        return {"enabled": False, "reason": "", "message": ""}
    return {
        "enabled": bool(service_mode.get("enabled")),
        "reason": str(service_mode.get("reason") or "").strip(),
        "message": str(service_mode.get("message") or "").strip(),
    }


def _service_mode_block_detail() -> str:
    service_mode = _load_service_mode()
    message = str(service_mode.get("message") or "").strip()
    reason = str(service_mode.get("reason") or "").strip()
    base = message or "Verlyn is currently out of service for maintenance."
    if reason and reason.lower() not in base.lower():
        return f"{base} Reason: {reason}"
    return base


def _service_mode_gate_detail() -> str:
    from workflow.workflow_gate import evaluate_workflow_gate

    service_mode = _load_service_mode()
    fallback = _service_mode_block_detail()
    workflow_gate = evaluate_workflow_gate(
        str(REPO_ROOT),
        scope="access",
        access_context={
            "authenticated": True,
            "service_mode": service_mode,
            "service_mode_blocked": bool(service_mode.get("enabled")),
            "service_mode_detail": fallback,
        },
    )
    for gate in list(workflow_gate.get("gate_results") or []):
        if str(gate.get("status") or "").strip().lower() == "fail":
            return str(gate.get("summary") or fallback).strip() or fallback
    return fallback


def _repo_slug_for_helper() -> str:
    runtime = _repo_config().get("_runtime") if isinstance(_repo_config().get("_runtime"), dict) else {}
    configured = str(runtime.get("repo_slug") or "").strip()
    if configured:
        return configured
    from cli import _repo_slug as _cli_repo_slug

    return str(_cli_repo_slug(str(REPO_ROOT)) or "").strip()


def _resolve_repo_execution_profile_for_ai_diagnosis() -> dict[str, object]:
    try:
        from server.runtime_resolution import resolve_repo_execution_runtime
        from server.settings import load_web_settings
        from server.workspace import WorkspaceCatalog
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": f"helper_runtime_unavailable: {type(exc).__name__}: {exc}",
        }

    workspace_root = _configured_workspace_root() or str(REPO_ROOT)
    config_path = str((REPO_ROOT / "analyzer" / "config.yaml").resolve())
    try:
        settings = load_web_settings(config_path=config_path, workspace_root=workspace_root)
        catalog = WorkspaceCatalog(settings)
        repo_slug = _repo_slug_for_helper()
        repository = catalog.repository(repo_slug)
        if not isinstance(repository, dict):
            return {
                "status": "unavailable",
                "reason": f"Repository {repo_slug or 'unknown'} was not found in the current workspace catalog.",
            }
        resolved = resolve_repo_execution_runtime(settings, catalog, repository, repo_slug=repo_slug)
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": f"execution_profile_resolution_failed: {type(exc).__name__}: {exc}",
        }

    profile = resolved.get("profile") if isinstance(resolved.get("profile"), dict) else {}
    profile_id = str(resolved.get("profile_id") or "").strip() or None
    resolution_source = str(
        ((resolved.get("execution_context") if isinstance(resolved.get("execution_context"), dict) else {}) or {}).get("resolution_source")
        or ""
    ).strip() or None
    provider = str(profile.get("provider") or "").strip().lower() or None
    if not profile_id or not provider:
        return {
            "status": "unavailable",
            "reason": "The repo execution profile resolved without a usable provider or profile id.",
        }
    return {
        "status": "ready",
        "repo_slug": repo_slug,
        "profile_id": profile_id,
        "resolution_source": resolution_source,
        "provider": provider,
        "profile": dict(profile),
    }


def _parse_route_repair_ai_payload(raw_text: str) -> dict[str, object]:
    try:
        parsed = json.loads(str(raw_text or "").strip() or "{}")
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    summary = str(parsed.get("summary") or "").strip()
    suggestions = [
        str(item).strip()
        for item in list(parsed.get("suggested_repairs") or [])
        if str(item).strip()
    ]
    risk_note = str(parsed.get("risk_note") or "").strip()
    if not summary:
        summary = str(raw_text or "").strip()
    return {
        "summary": summary,
        "suggested_repairs": suggestions[:3],
        "risk_note": risk_note or None,
    }


def _build_route_repair_ai_diagnosis(
    *,
    change_id: str | None,
    route_payload: dict[str, object],
    guidance: dict[str, object],
    auto_heal_error: str,
) -> dict[str, object]:
    resolved = _resolve_repo_execution_profile_for_ai_diagnosis()
    if str(resolved.get("status") or "").strip().lower() != "ready":
        return {
            "status": "unavailable",
            "reason": str(resolved.get("reason") or "AI diagnosis could not resolve a usable execution profile.").strip(),
        }

    try:
        from analyzer.llm import configure_llm, generate_text_sync, inspect_provider_connection, resolve_model
        from server.runtime_settings import apply_runtime_environment
    except Exception as exc:
        return {
            "status": "failed",
            "reason": f"ai_runtime_import_failed: {type(exc).__name__}: {exc}",
            "resolved_profile_id": resolved.get("profile_id"),
            "resolution_source": resolved.get("resolution_source"),
            "provider": resolved.get("provider"),
        }

    profile = dict(resolved.get("profile") or {})
    provider = str(resolved.get("provider") or "").strip().lower()
    profile_id = str(resolved.get("profile_id") or "").strip() or None
    runtime_settings = {
        "active_execution_profile_id": profile_id,
        "execution_profiles": {profile_id: profile} if profile_id else {},
    }

    try:
        apply_runtime_environment(runtime_settings, _repo_config())
        configure_llm(provider)
        model = resolve_model(((profile.get("model_overrides") or {}).get("task_execution")), tier="deep", provider=provider)
        provider_diagnostics = inspect_provider_connection(provider=provider, model=model)
        provider_status = str(provider_diagnostics.get("status") or "").strip().lower()
        if provider_status != "ok":
            return {
                "status": "unavailable",
                "reason": "The resolved AI provider is not ready for route diagnosis.",
                "resolved_profile_id": profile_id,
                "resolution_source": resolved.get("resolution_source"),
                "provider": provider,
                "provider_diagnostics": provider_diagnostics,
            }
        system_prompt = (
            "You explain blocked Verlyn route self-heal outcomes.\n"
            "Return JSON only.\n"
            "Never claim the git state is safe when the deterministic gate stopped.\n"
            "Do not recommend destructive commands such as git reset --hard, forced checkout, or dropping local changes.\n"
            "Prefer practical next steps that preserve work and help the operator decide what to inspect.\n"
            "Schema:\n"
            "{\n"
            '  "summary": "one short paragraph explaining what likely happened",\n'
            '  "suggested_repairs": ["short actionable next step"],\n'
            '  "risk_note": "one short note about what could go wrong if the operator guesses"\n'
            "}\n"
        )
        user_message = json.dumps(
            {
                "change_id": change_id,
                "route_status": route_payload.get("status"),
                "route_summary": route_payload.get("summary"),
                "current_branch": route_payload.get("current_branch"),
                "recorded_branch_name": route_payload.get("recorded_branch_name"),
                "auto_heal_failure_kind": guidance.get("failure_kind"),
                "auto_heal_error": str(auto_heal_error or "").strip(),
                "deterministic_summary": guidance.get("summary"),
                "deterministic_repair_options": list(guidance.get("repair_options") or []),
            },
            indent=2,
        )
        raw_text = generate_text_sync(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            max_output_tokens=900,
            repo_root=Path.cwd(),
        )
        ai_payload = _parse_route_repair_ai_payload(raw_text)
    except Exception as exc:
        return {
            "status": "failed",
            "reason": f"{type(exc).__name__}: {exc}",
            "resolved_profile_id": profile_id,
            "resolution_source": resolved.get("resolution_source"),
            "provider": provider,
        }

    return {
        "status": "generated",
        "resolved_profile_id": profile_id,
        "resolution_source": resolved.get("resolution_source"),
        "provider": provider,
        "model": model,
        "provider_diagnostics": provider_diagnostics,
        "summary": ai_payload.get("summary"),
        "suggested_repairs": list(ai_payload.get("suggested_repairs") or []),
        "risk_note": ai_payload.get("risk_note"),
    }


def _legacy_save_route_state(payload: dict[str, str | None]) -> None:
    raise AssistantRouteStateError(
        operation="save",
        cause=RuntimeError("Assistant edit routes are DB-backed; repo-local route fallback writes are disabled."),
    )


def _legacy_load_route_state() -> dict[str, str | None] | None:
    if not ASSISTANT_ROUTE_PATH.exists() or not ASSISTANT_ROUTE_PATH.is_file():
        return None
    try:
        payload = json.loads(ASSISTANT_ROUTE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    route_kind = str(payload.get("route_kind") or "").strip()
    if route_kind not in {"active_change", "direct_work"}:
        return None
    return {
        "route_kind": route_kind,
        "change_id": str(payload.get("change_id") or "").strip() or None,
        "reason": str(payload.get("reason") or "").strip() or None,
        "source": str(payload.get("source") or "").strip() or None,
        "recorded_at": str(payload.get("recorded_at") or "").strip() or None,
        "recorded_branch_name": str(payload.get("recorded_branch_name") or "").strip() or None,
    }


def _legacy_clear_route_state() -> None:
    try:
        ASSISTANT_ROUTE_PATH.unlink()
    except FileNotFoundError:
        return


class AssistantRouteStateError(RuntimeError):
    """Raised when helper route persistence fails after the underlying command succeeds."""

    def __init__(self, *, operation: str, cause: BaseException) -> None:
        self.operation = operation
        self.cause = cause
        message = str(cause).strip() or f"Could not {operation} the assistant edit route."
        super().__init__(
            f"{message} The underlying Verlyn command may have completed, but the helper did not record a safe edit route."
        )


def _route_state_error_details(exc: AssistantRouteStateError) -> dict[str, object]:
    cause = exc.cause
    details: dict[str, object] = {
        "operation": exc.operation,
        "cause_type": type(cause).__name__,
    }
    for attr_name in ("attempts", "retryable", "sqlstate", "operation"):
        if hasattr(cause, attr_name):
            details[attr_name] = getattr(cause, attr_name)
    return details


def _assistant_route_workspace_root() -> Path:
    configured_workspace = _configured_workspace_root()
    if configured_workspace:
        return Path(configured_workspace).expanduser().resolve()
    return REPO_ROOT.resolve()


def _assistant_route_store_dsn() -> str | None:
    try:
        installed_home = _installed_verlyn_home()
        if installed_home is not None and str(installed_home) not in sys.path:
            sys.path.insert(0, str(installed_home))
        from workflow.project_store.postgresql import resolve_postgresql_project_store_connection

        resolved = resolve_postgresql_project_store_connection(_repo_config())
    except Exception:
        return None
    dsn = str(resolved.get("dsn") or "").strip() if isinstance(resolved, dict) else ""
    return dsn or None


def _assistant_route_store_module():
    installed_home = _installed_verlyn_home()
    if installed_home is not None and str(installed_home) not in sys.path:
        sys.path.insert(0, str(installed_home))
    from workflow.project_store import assistant_edit_routes

    return assistant_edit_routes


def _save_route_state(payload: dict[str, str | None]) -> None:
    dsn = _assistant_route_store_dsn()
    if not dsn:
        raise AssistantRouteStateError(
            operation="save",
            cause=RuntimeError("Assistant edit routes are DB-backed; no route-store DSN is configured."),
        )
    operator_username = _require_assistant_operator_value(operation="save")
    route_store = _assistant_route_store_module()
    try:
        route_store.save_assistant_edit_route(
            dsn,
            workspace_root=_assistant_route_workspace_root(),
            repository_root=REPO_ROOT,
            operator_username=operator_username,
            payload=payload,
        )
    except Exception as exc:
        raise AssistantRouteStateError(operation="save", cause=exc) from exc
    _legacy_clear_route_state()


def _load_route_state() -> dict[str, str | None] | None:
    dsn = _assistant_route_store_dsn()
    if dsn:
        operator_username = _require_assistant_operator_value(operation="load")
        route_store = _assistant_route_store_module()
        payload = route_store.load_assistant_edit_route(
            dsn,
            workspace_root=_assistant_route_workspace_root(),
            repository_root=REPO_ROOT,
            operator_username=operator_username,
        )
        if isinstance(payload, dict):
            route_kind = str(payload.get("route_kind") or "").strip()
            if route_kind in {"active_change", "direct_work"}:
                _legacy_clear_route_state()
                return {
                    "route_kind": route_kind,
                    "change_id": str(payload.get("change_id") or "").strip() or None,
                    "reason": str(payload.get("reason") or "").strip() or None,
                    "source": str(payload.get("source") or "").strip() or None,
                    "recorded_at": str(payload.get("recorded_at") or "").strip() or None,
                    "recorded_branch_name": str(payload.get("recorded_branch_name") or "").strip() or None,
                }
        _legacy_clear_route_state()
        return None
    _legacy_clear_route_state()
    return None


def _clear_route_state() -> None:
    dsn = _assistant_route_store_dsn()
    if dsn:
        operator_username = _require_assistant_operator_value(operation="clear")
        route_store = _assistant_route_store_module()
        try:
            route_store.clear_assistant_edit_route(
                dsn,
                workspace_root=_assistant_route_workspace_root(),
                repository_root=REPO_ROOT,
                operator_username=operator_username,
            )
        except Exception as exc:
            raise AssistantRouteStateError(operation="clear", cause=exc) from exc
    _legacy_clear_route_state()


def _set_active_change_route(change_id: str, *, source: str) -> dict[str, str | None]:
    payload = {
        "route_kind": "active_change",
        "change_id": str(change_id or "").strip() or None,
        "reason": None,
        "source": source,
        "recorded_at": _now_iso(),
        "recorded_branch_name": _git_current_branch(),
    }
    _save_route_state(payload)
    return payload


def _set_direct_work_route(reason: str, *, source: str) -> dict[str, str | None]:
    payload = {
        "route_kind": "direct_work",
        "change_id": None,
        "reason": str(reason or "").strip() or None,
        "source": source,
        "recorded_at": _now_iso(),
    }
    _save_route_state(payload)
    return payload


def _extract_change_id_from_stdout(stdout: str) -> str | None:
    try:
        payload = json.loads(str(stdout or "").strip() or "{}")
    except Exception:
        payload = None
    if isinstance(payload, dict):
        direct_change_id = str(payload.get("change_id") or "").strip()
        if direct_change_id:
            return direct_change_id
        nested_change = payload.get("change")
        if isinstance(nested_change, dict):
            nested_change_id = str(nested_change.get("change_id") or "").strip()
            if nested_change_id:
                return nested_change_id
    for line in str(stdout or "").splitlines():
        if not line.startswith("Change:"):
            continue
        change_id = line.split("Change:", 1)[1].strip()
        if change_id:
            return change_id
    return None


HELPER_COMMAND_ALIASES: dict[str, str] = {
    "work-item": "task",
    "pickup-work-item": "pickup-task",
    "work-item-proposals": "proposals",
    "promote-work-item-proposal": "promote-proposal",
}

HELPER_CHANGES_SUBCOMMAND_ALIASES: dict[str, str] = {
    "work-item": "task",
    "move-work-item": "move-task",
}


def _normalize_helper_command(subcommand: str, args: list[str]) -> tuple[str, list[str]]:
    normalized_subcommand = HELPER_COMMAND_ALIASES.get(subcommand, subcommand)
    normalized_args = list(args or [])
    if normalized_subcommand == "changes":
        if not normalized_args or str(normalized_args[0] or "").startswith("-"):
            return normalized_subcommand, ["list", *normalized_args]
        normalized_args[0] = HELPER_CHANGES_SUBCOMMAND_ALIASES.get(normalized_args[0], normalized_args[0])
        return normalized_subcommand, normalized_args
    if normalized_subcommand == "change" and "--json" in normalized_args:
        non_json_args = [value for value in normalized_args if value != "--json"]
        if len(non_json_args) == 1 and not str(non_json_args[0] or "").startswith("-"):
            return "changes", ["show", non_json_args[0], "--json"]
    return normalized_subcommand, normalized_args


def _underlying_verlyn_command(subcommand: str, args: list[str]) -> list[str]:
    verlyn_command = _verlyn_command()
    if not verlyn_command:
        raise RuntimeError(
            "Verlyn CLI was not found. Install Verlyn or repair the repo-local workflow pack from the central Verlyn checkout."
        )
    if subcommand == "workflow-gate":
        return [*verlyn_command, "--target", str(REPO_ROOT), "workflow-gate", *args]
    if subcommand == "changes":
        return [*verlyn_command, "--target", str(REPO_ROOT), "changes", *args]
    if subcommand == "proposals":
        return [*verlyn_command, "--target", str(REPO_ROOT), "work-item-proposals", *args]
    if subcommand == "promote-proposal":
        return [*verlyn_command, "--target", str(REPO_ROOT), "promote-work-item-proposal", *args]
    return [*verlyn_command, "--target", str(REPO_ROOT), "workflow", subcommand, *args]


def _run_underlying_verlyn(
    subcommand: str,
    args: list[str],
    *,
    emit_output: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = _underlying_verlyn_command(subcommand, args)
    return _run(command, emit_output=emit_output, capture_output=capture_output)


def _should_stream_underlying_output(subcommand: str, args: list[str]) -> bool:
    if subcommand == "deliver-change" and "--json" not in args:
        return True
    if subcommand == "handoff-review" and "--json" not in args:
        return True
    if subcommand == "prepare-pr" and "--json" not in args:
        return True
    if subcommand == "publish-pr" and "--json" not in args and "--apply" in {str(item or "").strip().lower() for item in list(args or [])}:
        return True
    return False


def _json_mode_requested(args: list[str]) -> bool:
    return "--json" in list(args or [])


def _option_value(args: list[str], option_name: str) -> str | None:
    normalized_args = list(args or [])
    for index, value in enumerate(normalized_args):
        if str(value or "").strip() == option_name and index + 1 < len(normalized_args):
            candidate = str(normalized_args[index + 1] or "").strip()
            return candidate or None
    return None


def _strip_explicit_assistant_operator_args(args: list[str]) -> tuple[str | None, list[str]]:
    cleaned: list[str] = []
    explicit_operator: str | None = None
    iterator = iter(list(args or []))
    for raw in iterator:
        value = str(raw or "").strip()
        if value == "--as-user":
            explicit_operator = str(next(iterator, "") or "").strip() or explicit_operator
            continue
        if value.startswith("--as-user="):
            explicit_operator = value.split("=", 1)[1].strip() or explicit_operator
            continue
        cleaned.append(raw)
    return explicit_operator, cleaned


def _authenticated_cli_operator_value() -> str | None:
    try:
        import cli as verlyn_cli

        auth_context = verlyn_cli._cli_auth_context_for_workflow_command(  # type: ignore[attr-defined]
            _repo_config(),
            workspace_root=str(REPO_ROOT),
            command_label="Repo-local helper route",
            require_auth=True,
        )
        identity = getattr(auth_context, "identity", None)
        username = getattr(identity, "username", None)
    except Exception:
        return None
    return str(username or "").strip() or None


def _assistant_operator_value() -> str | None:
    explicit_operator = str(os.environ.get("VERLYN_ASSISTANT_OPERATOR") or "").strip()
    if explicit_operator:
        return explicit_operator
    return _authenticated_cli_operator_value()


def _require_assistant_operator_value(*, operation: str) -> str:
    operator = _assistant_operator_value()
    if operator:
        return operator
    raise AssistantRouteStateError(
        operation=operation,
        cause=RuntimeError(
            "Assistant edit routes are scoped to the authenticated CLI user. "
            "Run `verlyn auth login` before using route self-heal, or pass --as-user only for an explicit delegated override."
        ),
    )


def _changes_list_uses_mine_scope(args: list[str]) -> bool:
    normalized_args = list(args or [])
    nested = str((normalized_args[0] if normalized_args else "list") or "").strip().lower()
    if nested not in {"", "list"}:
        return False
    owner_scope = str(_option_value(normalized_args, "--owner-scope") or "mine").strip().lower()
    return owner_scope == "mine"


def _helper_command_requires_assistant_operator(subcommand: str, args: list[str]) -> bool:
    _ = subcommand, args
    return False


def _emit_helper_json(payload: dict[str, object]) -> None:
    sys.stdout.write(f"{json.dumps(payload, indent=2)}\n")


def _emit_helper_json_error(
    code: str,
    message: str,
    *,
    details: dict[str, object] | None = None,
    returncode: int = 1,
) -> int:
    payload: dict[str, object] = {
        "ok": False,
        "error": {
            "code": str(code or "").strip() or "workflow_helper_error",
            "message": str(message or "").strip() or "Repo-local workflow helper failed.",
        },
    }
    if isinstance(details, dict) and details:
        payload["error"]["details"] = details
    payload["returncode"] = int(returncode)
    _emit_helper_json(payload)
    return int(returncode)


def _change_exists(change_id: str) -> bool:
    normalized_change_id = str(change_id or "").strip()
    if not normalized_change_id:
        return False
    return _load_change_record_payload(normalized_change_id) is not None


def _git_current_branch() -> str | None:
    result = _run(["git", "branch", "--show-current"], emit_output=False)
    if result.returncode != 0:
        return None
    branch_name = str(result.stdout or "").strip()
    return branch_name or None


def _load_change_record_payload(change_id: str) -> dict[str, object] | None:
    normalized_change_id = str(change_id or "").strip()
    if not normalized_change_id:
        return None
    if normalized_change_id in _CHANGE_RECORD_PAYLOAD_CACHE:
        cached_payload = _CHANGE_RECORD_PAYLOAD_CACHE[normalized_change_id]
        return dict(cached_payload) if isinstance(cached_payload, dict) else None
    payload_map = _db_backed_change_payload_map()
    if payload_map is not None:
        payload = payload_map.get(normalized_change_id)
        if isinstance(payload, dict):
            _CHANGE_RECORD_PAYLOAD_CACHE[normalized_change_id] = dict(payload)
            return dict(payload)
    detail_payload = _load_explicit_change_payload(normalized_change_id)
    if isinstance(detail_payload, dict):
        _CHANGE_RECORD_PAYLOAD_CACHE[normalized_change_id] = dict(detail_payload)
        return dict(detail_payload)
    _CHANGE_RECORD_PAYLOAD_CACHE[normalized_change_id] = None
    return None


def _load_explicit_change_payload(change_id: str) -> dict[str, object] | None:
    result = _run_underlying_verlyn("changes", ["show", change_id, "--json"], emit_output=False)
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout or "{}")
    except Exception:
        return None
    change_payload = payload.get("change") if isinstance(payload, dict) else None
    return change_payload if isinstance(change_payload, dict) else None


def _db_backed_change_payloads() -> list[dict[str, object]]:
    global _DB_CHANGE_PAYLOADS_CACHE
    if _DB_CHANGE_PAYLOADS_CACHE is not None:
        return list(_DB_CHANGE_PAYLOADS_CACHE)
    # Route checks only need summary metadata such as status and branch binding.
    result = _run_underlying_verlyn(
        "changes",
        ["list", "--json", "--detail", "summary", "--all", "--owner-scope", "all"],
        emit_output=False,
    )
    if result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout or "{}")
    except Exception:
        return []
    payloads: list[dict[str, object]] = []
    for item in list(payload.get("changes") or []):
        if isinstance(item, dict):
            payloads.append(item)
    _DB_CHANGE_PAYLOADS_CACHE = list(payloads)
    return list(_DB_CHANGE_PAYLOADS_CACHE)


def _db_backed_change_payload_map() -> dict[str, dict[str, object]] | None:
    global _DB_CHANGE_PAYLOAD_MAP_CACHE
    if _DB_CHANGE_PAYLOAD_MAP_CACHE is not None:
        return _DB_CHANGE_PAYLOAD_MAP_CACHE
    payloads = _db_backed_change_payloads()
    if not payloads:
        return None
    payload_map: dict[str, dict[str, object]] = {}
    for payload in payloads:
        change_id = str(payload.get("change_id") or "").strip()
        if change_id:
            payload_map[change_id] = payload
    _DB_CHANGE_PAYLOAD_MAP_CACHE = payload_map
    return _DB_CHANGE_PAYLOAD_MAP_CACHE


def _change_status_from_payload(payload: dict[str, object] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    status = str(payload.get("status") or "").strip().lower()
    return status or None


def _raw_branch_binding_for_payload(payload: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    branch_payload = payload.get("branch")
    if isinstance(branch_payload, dict):
        return branch_payload
    workflow = payload.get("workflow")
    if isinstance(workflow, dict):
        workflow_branch = workflow.get("branch")
        if isinstance(workflow_branch, dict):
            return workflow_branch
    return {}


def _planned_branch_for_payload(payload: dict[str, object] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    branch_payload = _raw_branch_binding_for_payload(payload)
    if isinstance(branch_payload, dict):
        branch_name = str(branch_payload.get("branch_name") or "").strip()
        if branch_name:
            return branch_name
    metadata = payload.get("change_record_metadata")
    if isinstance(metadata, dict):
        branch_name = str(metadata.get("branch_name") or "").strip()
        if branch_name:
            return branch_name
    return None


def _route_branch_state_for_payload(payload: dict[str, object] | None) -> dict[str, object]:
    branch_name = _planned_branch_for_payload(payload)
    branch_payload = _raw_branch_binding_for_payload(payload)
    branch_status = str(branch_payload.get("status") or "").strip().lower()
    branch_exists = _git_branch_exists(branch_name)
    current_branch = _git_current_branch()
    current_branch_matches = bool(branch_name and current_branch == branch_name)
    route_attachable = bool(branch_name and (branch_exists or current_branch_matches))
    return {
        "branch_name": branch_name,
        "branch_status": branch_status or None,
        "branch_exists": branch_exists,
        "current_branch_matches": current_branch_matches,
        "route_attachable": route_attachable,
        "planned_only": bool(branch_name and not route_attachable),
    }


def _change_status(change_id: str | None) -> str | None:
    if not change_id:
        return None
    return _change_status_from_payload(_load_change_record_payload(change_id))


def _change_is_editable(change_id: str | None) -> bool:
    status = _change_status(change_id)
    if not status:
        return False
    return status not in NON_EDITABLE_CHANGE_STATUSES


def _raw_branch_binding_for_change(change_id: str | None) -> dict[str, object]:
    if not change_id:
        return {}
    return _raw_branch_binding_for_payload(_load_change_record_payload(change_id))


def _planned_branch_for_change(change_id: str | None) -> str | None:
    if not change_id:
        return None
    return _planned_branch_for_payload(_load_change_record_payload(change_id))


def _git_branch_exists(branch_name: str | None) -> bool:
    normalized_branch_name = str(branch_name or "").strip()
    if not normalized_branch_name:
        return False
    result = _run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{normalized_branch_name}"],
        emit_output=False,
    )
    return result.returncode == 0


def _route_branch_state_for_change(change_id: str | None) -> dict[str, object]:
    return _route_branch_state_for_payload(_load_change_record_payload(change_id))


def _bound_branch_for_change(change_id: str | None) -> str | None:
    branch_state = _route_branch_state_for_change(change_id)
    if branch_state.get("route_attachable"):
        return str(branch_state.get("branch_name") or "").strip() or None
    return None


def _normalized_operator(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized or None


def _change_owner_for_payload(payload: dict[str, object]) -> str | None:
    workflow = payload.get("workflow")
    if isinstance(workflow, dict):
        owner = str(workflow.get("workflow_owner") or "").strip()
        if owner:
            return owner
    for key in ("workflow_owner", "owner"):
        owner = str(payload.get(key) or "").strip()
        if owner:
            return owner
    created_by = payload.get("created_by")
    if isinstance(created_by, dict):
        owner = str(created_by.get("username") or created_by.get("profile_id") or "").strip()
        if owner:
            return owner
    return None


def _change_payload_matches_operator(payload: dict[str, object], operator_username: str | None) -> bool:
    normalized_operator = _normalized_operator(operator_username)
    if not normalized_operator:
        return False
    owner = _normalized_operator(_change_owner_for_payload(payload))
    if not owner:
        return False
    return owner == normalized_operator


def _changes_bound_to_branch(branch_name: str | None) -> list[str]:
    normalized_branch_name = str(branch_name or "").strip()
    if not normalized_branch_name:
        return []
    operator_username = _assistant_operator_value()
    matches: list[str] = []
    for payload in _db_backed_change_payloads():
        status = _change_status_from_payload(payload)
        if status in NON_EDITABLE_CHANGE_STATUSES:
            continue
        if not _change_payload_matches_operator(payload, operator_username):
            continue
        change_id = str(payload.get("change_id") or "").strip()
        if not change_id:
            continue
        branch_state = _route_branch_state_for_payload(payload)
        bound_branch_name = str(branch_state.get("branch_name") or "").strip()
        if bound_branch_name == normalized_branch_name and bool(branch_state.get("route_attachable")):
            matches.append(change_id)
    return matches


def _missing_work_branch_payload(
    *,
    change_id: str | None,
    recorded_at: str | None,
    source: str | None,
) -> dict[str, object]:
    current_branch = _git_current_branch()
    branch_state = _route_branch_state_for_change(change_id)
    planned_branch_name = str(branch_state.get("branch_name") or "").strip() or None
    branch_change_candidates = _changes_bound_to_branch(current_branch)
    branch_change_id = branch_change_candidates[0] if len(branch_change_candidates) == 1 else None
    if planned_branch_name:
        summary = (
            f"Active change route {change_id or 'unknown'} still points at planned work branch "
            f"{planned_branch_name}, but that branch is not available locally yet."
        )
        next_step = (
            f"Create or bind `{planned_branch_name}` before editing, then rerun "
            "`python scripts/verlyn_workflow.py assert-edit-route`."
        )
    else:
        summary = f"Active change route {change_id or 'unknown'} does not have a usable work branch yet."
        next_step = (
            "Create or bind a work branch for this change before editing, then rerun "
            "`python scripts/verlyn_workflow.py assert-edit-route`."
        )
    return {
        "status": "blocked_missing_work_branch",
        "allowed": False,
        "change_id": change_id,
        "reason": None,
        "recorded_at": recorded_at,
        "source": source,
        "summary": summary,
        "next_step": next_step,
        "current_branch": current_branch,
        "recorded_branch_name": planned_branch_name,
        "branch_change_id": branch_change_id,
        "branch_change_candidates": branch_change_candidates,
    }


def _branch_route_drift_payload(
    *,
    change_id: str | None,
    recorded_at: str | None,
    source: str | None,
) -> dict[str, object]:
    current_branch = _git_current_branch()
    recorded_branch_name = _bound_branch_for_change(change_id)
    branch_change_candidates = _changes_bound_to_branch(current_branch)
    branch_change_id = branch_change_candidates[0] if len(branch_change_candidates) == 1 else None
    if not current_branch:
        summary = f"Active change route {change_id or 'unknown'} could not be aligned because the current git branch is unavailable."
        next_step = "Check out the intended work branch, then run `python scripts/verlyn_workflow.py use-change <change-id>` again."
    elif len(branch_change_candidates) > 1:
        blockers = ", ".join(branch_change_candidates)
        summary = (
            f"Active change route {change_id or 'unknown'} does not match the current branch {current_branch}, "
            f"and that branch is bound to multiple changes: {blockers}."
        )
        next_step = (
            f"Switch to the intended branch for {change_id or 'this change'} or rebind the current branch so only one change owns `{current_branch}`."
        )
    elif branch_change_id:
        summary = (
            f"Active change route {change_id or 'unknown'} is bound to {recorded_branch_name or 'an unknown branch'}, "
            f"but the current branch {current_branch} is bound to {branch_change_id}."
        )
        next_step = (
            f"Switch back to `{recorded_branch_name}` or run `python scripts/verlyn_workflow.py use-change {branch_change_id}` "
            f"to align the repo-local route with `{current_branch}`."
        )
    else:
        summary = (
            f"Active change route {change_id or 'unknown'} is bound to {recorded_branch_name or 'an unknown branch'}, "
            f"but the current branch is {current_branch}."
        )
        next_step = (
            f"Switch back to `{recorded_branch_name}` or bind `{current_branch}` to the intended change before continuing."
        )
    return {
        "status": "blocked_branch_route_drift",
        "allowed": False,
        "change_id": change_id,
        "reason": None,
        "recorded_at": recorded_at,
        "source": source,
        "summary": summary,
        "next_step": next_step,
        "current_branch": current_branch,
        "recorded_branch_name": recorded_branch_name,
        "branch_change_id": branch_change_id,
        "branch_change_candidates": branch_change_candidates,
    }


def _planning_only_change_route_payload(
    *,
    change_id: str | None,
    recorded_at: str | None,
    source: str | None,
) -> dict[str, object]:
    current_branch = _git_current_branch()
    normalized_change_id = str(change_id or "").strip() or None
    return {
        "status": "blocked_planning_change_route",
        "allowed": False,
        "change_id": normalized_change_id,
        "reason": "draft",
        "recorded_at": recorded_at,
        "source": source,
        "summary": (
            f"Change {normalized_change_id or 'unknown'} is draft and selected for planning only. "
            "Activate the change before editing source files or creating a work branch."
        ),
        "next_step": (
            f"Run `python scripts/verlyn_workflow.py changes activate {normalized_change_id}` before editing."
            if normalized_change_id
            else "Select or activate a change before editing."
        ),
        "current_branch": current_branch,
        "recorded_branch_name": None,
        "branch_change_id": None,
        "branch_change_candidates": _changes_bound_to_branch(current_branch),
    }


def _resolve_editing_route(explicit_change_id: str | None = None) -> dict[str, object]:
    if explicit_change_id:
        normalized_change_id = str(explicit_change_id).strip()
        exists = _change_exists(normalized_change_id)
        if exists:
            if _change_status(normalized_change_id) in PLANNING_ONLY_CHANGE_ROUTE_STATUSES:
                return _planning_only_change_route_payload(
                    change_id=normalized_change_id,
                    recorded_at=None,
                    source="explicit_change_id",
                )
            branch_state = _route_branch_state_for_change(normalized_change_id)
            recorded_branch_name = str(branch_state.get("branch_name") or "").strip() or None
            current_branch = _git_current_branch()
            if branch_state.get("planned_only"):
                return _missing_work_branch_payload(
                    change_id=normalized_change_id,
                    recorded_at=None,
                    source="explicit_change_id",
                )
            if recorded_branch_name and current_branch and current_branch != recorded_branch_name:
                return _branch_route_drift_payload(
                    change_id=normalized_change_id,
                    recorded_at=None,
                    source="explicit_change_id",
                )
        return {
            "status": "active_change" if exists else "missing_change_record",
            "allowed": bool(exists),
            "change_id": normalized_change_id,
            "reason": None,
            "recorded_at": None,
            "source": "explicit_change_id",
            "summary": (
                f"Active change route is {normalized_change_id}."
                if exists
                else f"Recorded change route {normalized_change_id} no longer exists."
            ),
            "next_step": None if exists else "Pick an existing change with `python scripts/verlyn_workflow.py use-change <change-id>`.",
            "current_branch": _git_current_branch(),
            "recorded_branch_name": _bound_branch_for_change(normalized_change_id),
        }
    route_state = _load_route_state()
    if not route_state:
        current_branch = _git_current_branch()
        branch_change_candidates = _changes_bound_to_branch(current_branch)
        branch_change_id = branch_change_candidates[0] if len(branch_change_candidates) == 1 else None
        if branch_change_id:
            summary = (
                f"No active change route is recorded for this repo-local session, but the current branch {current_branch} is bound to {branch_change_id}."
            )
            next_step = f"Run `python scripts/verlyn_workflow.py use-change {branch_change_id}` to align the helper route with `{current_branch}`."
        elif len(branch_change_candidates) > 1:
            blockers = ", ".join(branch_change_candidates)
            summary = (
                f"No active change route is recorded for this repo-local session, and the current branch {current_branch} is bound to multiple changes: {blockers}."
            )
            next_step = (
                f"Switch to the intended work branch or rebind `{current_branch}` so only one change owns it before continuing."
            )
        else:
            summary = "No active change route or explicit direct-work route is recorded for this repo-local session."
            next_step = (
                "Run `python scripts/verlyn_workflow.py use-change <change-id>` or "
                "`python scripts/verlyn_workflow.py direct-work --reason \"...\"` before code edits."
            )
        return {
            "status": "blocked_missing_change",
            "allowed": False,
            "change_id": None,
            "reason": None,
            "recorded_at": None,
            "source": None,
            "summary": summary,
            "next_step": next_step,
            "current_branch": current_branch,
            "recorded_branch_name": None,
            "branch_change_id": branch_change_id,
            "branch_change_candidates": branch_change_candidates,
        }
    if route_state.get("route_kind") == "direct_work":
        reason = str(route_state.get("reason") or "").strip() or None
        return {
            "status": "direct_work_allowed",
            "allowed": True,
            "change_id": None,
            "reason": reason,
            "recorded_at": route_state.get("recorded_at"),
            "source": route_state.get("source"),
            "summary": f"Direct work route is active{f': {reason}' if reason else '.'}",
            "next_step": None,
            "current_branch": _git_current_branch(),
            "recorded_branch_name": None,
        }
    change_id = str(route_state.get("change_id") or "").strip() or None
    if change_id and _change_exists(change_id):
        if _change_status(change_id) in PLANNING_ONLY_CHANGE_ROUTE_STATUSES:
            return _planning_only_change_route_payload(
                change_id=change_id,
                recorded_at=route_state.get("recorded_at"),
                source=route_state.get("source"),
            )
        branch_state = _route_branch_state_for_change(change_id)
        recorded_branch_name = str(branch_state.get("branch_name") or "").strip() or None
        current_branch = _git_current_branch()
        if branch_state.get("planned_only"):
            return _missing_work_branch_payload(
                change_id=change_id,
                recorded_at=route_state.get("recorded_at"),
                source=route_state.get("source"),
            )
        if recorded_branch_name and current_branch and current_branch != recorded_branch_name:
            return _branch_route_drift_payload(
                change_id=change_id,
                recorded_at=route_state.get("recorded_at"),
                source=route_state.get("source"),
            )
        return {
            "status": "active_change",
            "allowed": True,
            "change_id": change_id,
            "reason": None,
            "recorded_at": route_state.get("recorded_at"),
            "source": route_state.get("source"),
            "summary": f"Active change route is {change_id}.",
            "next_step": None,
            "current_branch": current_branch,
            "recorded_branch_name": recorded_branch_name,
        }
    return {
        "status": "missing_change_record",
        "allowed": False,
        "change_id": change_id,
        "reason": None,
        "recorded_at": route_state.get("recorded_at"),
        "source": route_state.get("source"),
        "summary": f"Recorded change route {change_id or 'unknown'} no longer exists.",
        "next_step": "Pick an existing change with `python scripts/verlyn_workflow.py use-change <change-id>`.",
        "current_branch": _git_current_branch(),
        "recorded_branch_name": None,
    }


def _auto_reconcile_route_from_current_branch(
    route_payload: dict[str, object],
    *,
    source: str,
) -> dict[str, object] | None:
    status = str(route_payload.get("status") or "").strip().lower()
    current_change_id = str(route_payload.get("change_id") or "").strip() or None
    current_branch = str(route_payload.get("current_branch") or _git_current_branch() or "").strip() or None
    branch_change_candidates = route_payload.get("branch_change_candidates")
    if not isinstance(branch_change_candidates, list):
        branch_change_candidates = _changes_bound_to_branch(current_branch)
    branch_change_id = (
        str(branch_change_candidates[0] or "").strip() or None if len(branch_change_candidates) == 1 else None
    )
    if not branch_change_id or not _change_exists(branch_change_id):
        return None

    can_auto_reconcile = status in {"blocked_missing_change", "missing_change_record"}
    if not can_auto_reconcile and status in {"blocked_branch_route_drift", "blocked_missing_work_branch"}:
        can_auto_reconcile = bool(current_change_id and not _change_is_editable(current_change_id))
    if not can_auto_reconcile:
        return None

    _set_active_change_route(branch_change_id, source=source)
    reconciled_payload = _resolve_editing_route()
    if not reconciled_payload.get("allowed"):
        return None
    reconciled_payload["auto_reconciled"] = True
    reconciled_payload["reconciled_from_change_id"] = current_change_id
    reconciled_payload["reconciled_to_change_id"] = branch_change_id
    if status in {"blocked_branch_route_drift", "blocked_missing_work_branch"} and current_change_id:
        reconciled_payload["summary"] = (
            f"Auto-reconciled the active change route from closed or deferred change {current_change_id} "
            f"to {branch_change_id} because the current branch {current_branch} is uniquely bound to that change."
        )
    else:
        reconciled_payload["summary"] = (
            f"Auto-reconciled the active change route to {branch_change_id} because the current branch "
            f"{current_branch} is uniquely bound to that change."
        )
    reconciled_payload["next_step"] = None
    return reconciled_payload


def _attempt_self_heal_change_route(
    change_id: str | None,
    *,
    source: str,
    action: str,
) -> tuple[dict[str, object] | None, str | None]:
    normalized_change_id = str(change_id or "").strip() or None
    if not normalized_change_id or not _change_exists(normalized_change_id) or not _change_is_editable(normalized_change_id):
        return None, None
    try:
        from workflow.change_workspace import self_heal_change_work_branch

        repair = self_heal_change_work_branch(
            str(REPO_ROOT),
            normalized_change_id,
            action=action,
            binding_source=source,
            config=_repo_config(),
        )
    except Exception as exc:
        return None, str(exc).strip() or "Automatic branch repair failed."
    _clear_change_payload_caches()
    _set_active_change_route(normalized_change_id, source=source)
    reconciled_payload = _resolve_editing_route()
    if not reconciled_payload.get("allowed"):
        return None, None
    refresh_action = repair.get("refresh_action") if isinstance(repair, dict) else {}
    branch_action = repair.get("branch_action") if isinstance(repair, dict) else {}
    refresh_applied = bool(refresh_action.get("refresh_applied")) if isinstance(refresh_action, dict) else False
    branch_action_message = str((branch_action or {}).get("message") or "").strip()
    refresh_message = str((refresh_action or {}).get("message") or "").strip()
    reconciled_payload["auto_healed_branch"] = True
    reconciled_payload["branch_refresh_applied"] = refresh_applied
    reconciled_payload["summary"] = (
        f"Auto-healed the work branch for {normalized_change_id}. "
        f"{refresh_message or branch_action_message or f'Ready to continue {action}.'}"
    )
    reconciled_payload["next_step"] = None
    return reconciled_payload, None


def _auto_heal_failure_guidance(
    error: str,
    *,
    change_id: str | None,
    route_payload: dict[str, object],
) -> dict[str, object]:
    normalized_error = str(error or "").strip()
    lowered = normalized_error.lower()
    current_branch = str(route_payload.get("current_branch") or _git_current_branch() or "").strip() or None
    recorded_branch_name = str(route_payload.get("recorded_branch_name") or "").strip() or None
    normalized_change_id = str(change_id or route_payload.get("change_id") or "").strip() or "this change"

    failure_kind = "unknown"
    summary = (
        f"{route_payload.get('summary') or 'The repo-local edit route is blocked.'} "
        f"Verlyn tried to repair it automatically, but stopped because {normalized_error or 'the branch repair failed.'}"
    )
    repair_options: list[str] = []

    if "local changes could be lost" in lowered or "clean the working tree before refreshing" in lowered:
        failure_kind = "dirty_worktree"
        summary = (
            f"{route_payload.get('summary') or 'The repo-local edit route is blocked.'} "
            "Verlyn stopped before refreshing the work branch because the working tree is dirty and auto-heal could lose local changes."
        )
        repair_options = [
            (
                "Run `python scripts/verlyn_workflow.py refresh-change-branch "
                f"{normalized_change_id} --expected-dirty-path <path> --reason \"<reason>\" --dry-run` "
                "to preserve and refresh the dirty work through the governed helper."
            ),
            (
                f"Switch to `{recorded_branch_name}` and inspect the uncommitted work manually before asking Verlyn to refresh it again."
                if recorded_branch_name
                else f"Inspect the uncommitted work on `{current_branch}` manually before retrying."
            ),
        ]
    elif "manual conflict resolution" in lowered or "rebase was aborted" in lowered or "conflict" in lowered:
        failure_kind = "conflict_risk"
        summary = (
            f"{route_payload.get('summary') or 'The repo-local edit route is blocked.'} "
            "Verlyn stopped because refreshing the work branch would require manual conflict resolution."
        )
        repair_options = [
            (
                f"Manually update `{recorded_branch_name}` against its base branch, resolve conflicts, and rerun `python scripts/verlyn_workflow.py assert-edit-route`."
                if recorded_branch_name
                else "Manually resolve the branch drift, then rerun `python scripts/verlyn_workflow.py assert-edit-route`."
            ),
            "If you need help deciding between rebase and merge, inspect `git status` and `git log --oneline --decorate --graph --max-count=20` first.",
        ]
    elif "still appear active for this repository" in lowered or "index.lock" in lowered:
        failure_kind = "git_lock"
        summary = (
            f"{route_payload.get('summary') or 'The repo-local edit route is blocked.'} "
            "Verlyn stopped because live git activity or a lock file makes branch repair unsafe right now."
        )
        repair_options = [
            "Wait for the other git operation to finish, then rerun `python scripts/verlyn_workflow.py assert-edit-route`.",
            "If you believe the lock is stale, inspect `.git/index.lock` and the running git processes before retrying.",
        ]
    elif "does not have a planned work branch" in lowered or "branch_name is required" in lowered:
        failure_kind = "missing_branch_plan"
        summary = (
            f"{route_payload.get('summary') or 'The repo-local edit route is blocked.'} "
            f"Verlyn could not repair {normalized_change_id} because the change does not have a usable planned work branch."
        )
        repair_options = [
            f"Bind or create a work branch for {normalized_change_id}, then rerun `python scripts/verlyn_workflow.py use-change {normalized_change_id}`.",
            "If the change should not own a branch yet, keep the helper route on the current active change until the new branch is ready.",
        ]
    elif "did not match any file(s) known to git" in lowered or "is not available locally" in lowered:
        failure_kind = "missing_local_branch"
        summary = (
            f"{route_payload.get('summary') or 'The repo-local edit route is blocked.'} "
            "Verlyn could not repair the route because the expected work branch is not available locally."
        )
        repair_options = [
            (
                f"Create or fetch `{recorded_branch_name}`, then rerun `python scripts/verlyn_workflow.py assert-edit-route`."
                if recorded_branch_name
                else "Create or fetch the missing work branch, then rerun `python scripts/verlyn_workflow.py assert-edit-route`."
            ),
            f"If `{current_branch}` is the branch you intend to use, rebind the change to it before continuing." if current_branch else "Rebind the change to the intended local branch before continuing.",
        ]
    else:
        repair_options = [
            "Inspect `git status` and the change's bound branch, then rerun `python scripts/verlyn_workflow.py assert-edit-route`.",
            f"If the route should stay on a different change, run `python scripts/verlyn_workflow.py use-change {normalized_change_id}` after fixing the branch state.",
        ]

    next_step = repair_options[0] if repair_options else normalized_error or None
    return {
        "failure_kind": failure_kind,
        "summary": summary,
        "next_step": next_step,
        "repair_options": repair_options,
    }


def _attempt_route_self_heal(
    route_payload: dict[str, object],
    *,
    source: str,
    explicit_change_id: str | None = None,
    action: str,
) -> dict[str, object] | None:
    status = str(route_payload.get("status") or "").strip().lower()
    target_change_id = str(explicit_change_id or route_payload.get("change_id") or "").strip() or None
    allowed_statuses = {"blocked_missing_work_branch", "blocked_branch_route_drift"}
    if explicit_change_id:
        allowed_statuses.add("blocked_branch_route_target_mismatch")
    if status not in allowed_statuses:
        return None
    reconciled_payload, error = _attempt_self_heal_change_route(
        target_change_id,
        source=source,
        action=action,
    )
    if reconciled_payload is not None:
        reconciled_payload["auto_reconciled"] = True
        reconciled_payload["reconciled_from_change_id"] = route_payload.get("change_id")
        reconciled_payload["reconciled_to_change_id"] = target_change_id
        return reconciled_payload
    if not error:
        return None
    blocked_payload = dict(route_payload)
    guidance = _auto_heal_failure_guidance(
        error,
        change_id=target_change_id,
        route_payload=route_payload,
    )
    blocked_payload["auto_heal_attempted"] = True
    blocked_payload["auto_heal_error"] = error
    blocked_payload["auto_heal_failure_kind"] = guidance["failure_kind"]
    blocked_payload["repair_options"] = list(guidance.get("repair_options") or [])
    blocked_payload["summary"] = str(guidance.get("summary") or route_payload.get("summary") or "")
    blocked_payload["next_step"] = guidance.get("next_step")
    blocked_payload["ai_repair_diagnosis"] = _build_route_repair_ai_diagnosis(
        change_id=target_change_id,
        route_payload=route_payload,
        guidance=guidance,
        auto_heal_error=error,
    )
    return blocked_payload


def _route_preservation_note_for_created_change(change_id: str | None) -> str | None:
    normalized_change_id = str(change_id or "").strip() or None
    if not normalized_change_id:
        return None
    existing_route = _resolve_editing_route()
    if not existing_route.get("allowed"):
        return None
    existing_change_id = str(existing_route.get("change_id") or "").strip() or None
    if not existing_change_id or existing_change_id == normalized_change_id:
        return None
    current_branch = str(existing_route.get("current_branch") or _git_current_branch() or "").strip() or None
    branch_state = _route_branch_state_for_change(normalized_change_id)
    branch_name = str(branch_state.get("branch_name") or "").strip() or None
    if branch_state.get("route_attachable") and (not current_branch or branch_name == current_branch):
        return None
    if branch_name and current_branch and branch_name != current_branch:
        return (
            f"Note: created {normalized_change_id}, but kept the active change route on {existing_change_id} "
            f"because the new change is planned for {branch_name} while the current branch is {current_branch}. "
            f"Run `python scripts/verlyn_workflow.py use-change {normalized_change_id}` after switching or binding its work branch."
        )
    if branch_name:
        return (
            f"Note: created {normalized_change_id}, but kept the active change route on {existing_change_id} "
            f"because the new change only has the planned work branch {branch_name}. "
            f"Run `python scripts/verlyn_workflow.py use-change {normalized_change_id}` after switching or binding its work branch."
        )
    return (
        f"Note: created {normalized_change_id}, but kept the active change route on {existing_change_id} "
        f"until the new change has an attached work branch. "
        f"Run `python scripts/verlyn_workflow.py use-change {normalized_change_id}` when you are ready to switch."
    )


def _record_route_after_command(subcommand: str, args: list[str], result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode != 0:
        return
    normalized_args = list(args or [])
    positional_args = [value for value in normalized_args if str(value or "").strip() and not str(value or "").strip().startswith("-")]
    change_id: str | None = None
    route_preservation_note: str | None = None
    if subcommand == "start-change":
        for index, value in enumerate(normalized_args):
            if value == "--status" and index + 1 < len(normalized_args):
                if str(normalized_args[index + 1] or "").strip().lower() == "draft":
                    return
                break
        change_id = _extract_change_id_from_stdout(result.stdout) or (positional_args[0] if positional_args else None)
        route_preservation_note = _route_preservation_note_for_created_change(change_id)
    elif subcommand == "deliver-change":
        change_id = positional_args[0] if positional_args else None
        existing_route = _load_route_state()
        if existing_route and existing_route.get("route_kind") == "active_change" and existing_route.get("change_id") == change_id:
            _clear_route_state()
        return
    elif subcommand == "publish-pr":
        if "--apply" not in {str(item or "").strip().lower() for item in normalized_args}:
            return
        change_id = positional_args[0] if positional_args else None
    elif subcommand in {"change", "task", "pickup-task", "handoff-review", "prepare-pr"}:
        change_id = positional_args[0] if positional_args else None
    elif subcommand == "close-change":
        change_id = positional_args[0] if positional_args else None
        requested_status = "merged"
        for index, value in enumerate(normalized_args):
            if value == "--status" and index + 1 < len(normalized_args):
                requested_status = str(normalized_args[index + 1] or "").strip().lower()
                break
        if requested_status in TERMINAL_CHANGE_ROUTE_STATUSES:
            existing_route = _load_route_state()
            if existing_route and existing_route.get("route_kind") == "active_change" and existing_route.get("change_id") == change_id:
                _clear_route_state()
            return
    elif subcommand == "changes" and normalized_args:
        nested = normalized_args[0]
        if nested == "create":
            create_positional = [
                value
                for value in normalized_args[1:]
                if str(value or "").strip() and not str(value or "").strip().startswith("-")
            ]
            change_id = _extract_change_id_from_stdout(result.stdout) or (create_positional[0] if create_positional else None)
            route_preservation_note = _route_preservation_note_for_created_change(change_id)
        elif nested in {"update", "task"} and len(normalized_args) > 1:
            nested_positional = [
                value
                for value in normalized_args[1:]
                if str(value or "").strip() and not str(value or "").strip().startswith("-")
            ]
            change_id = nested_positional[0] if nested_positional else None
    if change_id:
        if route_preservation_note:
            sys.stderr.write(f"{route_preservation_note}\n")
            return
        if _change_status(change_id) in PLANNING_ONLY_CHANGE_ROUTE_STATUSES:
            sys.stderr.write(
                f"Note: {subcommand} updated draft change {change_id}, but did not activate it or create a work branch.\n"
            )
            return
        _set_active_change_route(change_id, source=f"helper:{subcommand}")


def _context_with_route(args: list[str]) -> int:
    result = _run_underlying_verlyn("context", args, emit_output=False)
    if result.returncode != 0:
        return int(result.returncode)
    explicit_change_id: str | None = None
    for index, value in enumerate(args):
        if value == "--change-id" and index + 1 < len(args):
            explicit_change_id = str(args[index + 1] or "").strip() or None
            break
    route_payload = _resolve_editing_route(explicit_change_id=explicit_change_id)
    governance_payload = _governance_reload_gate_payload()
    if "--json" in args:
        try:
            payload = json.loads(result.stdout or "{}")
        except Exception:
            sys.stderr.write("Error: workflow context did not emit valid JSON.\n")
            return 1
        payload["editing_route"] = route_payload
        payload["governance_reload"] = governance_payload
        sys.stdout.write(f"{json.dumps(payload, indent=2)}\n")
        return 0
    if result.stdout and not result.stdout.endswith("\n"):
        sys.stdout.write("\n")
    governance_notice = str(
        governance_payload.get("operator_notice") or governance_payload.get("summary") or ""
    ).strip()
    sys.stdout.write(f"Governance reload: {governance_notice}\n")
    if governance_payload.get("next_step"):
        sys.stdout.write(f"Next step:  {governance_payload['next_step']}\n")
    sys.stdout.write(f"Edit route: {route_payload['summary']}\n")
    if route_payload.get("next_step"):
        sys.stdout.write(f"Next step:  {route_payload['next_step']}\n")
    return 0


def _cmd_assistant_startup(args: list[str]) -> int:
    json_mode = "--json" in args
    payload = _assistant_startup_payload(source="helper:assistant-startup")
    if json_mode:
        sys.stdout.write(f"{json.dumps(payload, indent=2)}\n")
        return 0
    receipt = payload.get("governance_reload") if isinstance(payload.get("governance_reload"), dict) else {}
    notice = str(receipt.get("operator_notice") or receipt.get("summary") or "").strip()
    if notice:
        sys.stdout.write(f"Operator notice: {notice}\n")
    sys.stdout.write("Recorded assistant governance reload for this repo-local CLI session.\n")
    for item in list(payload.get("governance_files") or []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        exists = bool(item.get("exists"))
        state = "loaded" if exists else "missing"
        sys.stdout.write(f"- {path}: {state}\n")
    sys.stdout.write("Recommended startup read order:\n")
    for item in list(payload.get("startup_read_order") or []):
        sys.stdout.write(f"- {item}\n")
    receipt = payload.get("governance_reload") if isinstance(payload.get("governance_reload"), dict) else {}
    if receipt.get("receipt_path"):
        sys.stdout.write(f"Receipt: {_relative_repo_path(REPO_ROOT / str(receipt['receipt_path']))}\n")
    return 0


def _cmd_use_change(args: list[str]) -> int:
    change_id = str((args[0] if args else "") or "").strip()
    if not change_id:
        print("Error: change id is required.", file=sys.stderr)
        return 1
    if not _change_exists(change_id):
        print(f"Error: change {change_id} was not found in this repository.", file=sys.stderr)
        return 1
    if _change_status(change_id) in PLANNING_ONLY_CHANGE_ROUTE_STATUSES:
        try:
            _set_active_change_route(change_id, source="helper:use-change")
        except AssistantRouteStateError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(
            f"Selected draft change {change_id} for planning. "
            "No work branch was created or checked out; activate the change before editing."
        )
        return 0
    try:
        _set_active_change_route(change_id, source="helper:use-change")
    except AssistantRouteStateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Active change route set to {change_id}.")
    healed_payload = _attempt_route_self_heal(
        {
            "status": "blocked_missing_work_branch",
            "change_id": change_id,
            "current_branch": _git_current_branch(),
        },
        source="helper:auto-heal-use-change",
        explicit_change_id=change_id,
        action=f"preparing {change_id} for implementation",
    )
    if healed_payload is not None:
        if healed_payload.get("allowed"):
            print(str(healed_payload.get("summary") or ""), file=sys.stderr)
            return 0
        if healed_payload.get("auto_heal_attempted"):
            print(str(healed_payload.get("summary") or ""), file=sys.stderr)
    recorded_branch_name = _bound_branch_for_change(change_id)
    planned_branch_name = _planned_branch_for_change(change_id)
    current_branch = _git_current_branch()
    if recorded_branch_name and current_branch and recorded_branch_name != current_branch:
        print(
            f"Note: {change_id} is bound to {recorded_branch_name}, but the current branch is {current_branch}. "
            "Use `assert-edit-route` before editing or switch branches now.",
        )
    elif planned_branch_name and not recorded_branch_name:
        print(
            f"Note: {change_id} has planned work branch {planned_branch_name}, but that branch is not available locally yet. "
            "Create or bind it before editing.",
        )
    return 0


def _cmd_direct_work(args: list[str]) -> int:
    parsed = argparse.ArgumentParser(prog="verlyn_workflow.py direct-work")
    parsed.add_argument("--reason", required=True, help="Why direct work is allowed for this session")
    namespace = parsed.parse_args(args)
    try:
        _set_direct_work_route(namespace.reason, source="helper:direct-work")
    except AssistantRouteStateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Direct work route recorded: {namespace.reason}")
    return 0


def _cmd_clear_route() -> int:
    try:
        _clear_route_state()
    except AssistantRouteStateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print("Cleared the repo-local editing route.")
    return 0


def _cmd_assert_edit_route(args: list[str]) -> int:
    json_mode = "--json" in args
    governance_payload = _governance_reload_gate_payload()
    route_payload = _resolve_editing_route()
    if governance_payload.get("allowed") and not route_payload.get("allowed"):
        reconciled_payload = _auto_reconcile_route_from_current_branch(
            route_payload,
            source="helper:auto-reconcile-assert",
        )
        if reconciled_payload is not None:
            route_payload = reconciled_payload
    if governance_payload.get("allowed") and not route_payload.get("allowed"):
        healed_payload = _attempt_route_self_heal(
            route_payload,
            source="helper:auto-heal-assert",
            action="continuing implementation",
        )
        if healed_payload is not None:
            route_payload = healed_payload
    allowed = bool(governance_payload.get("allowed")) and bool(route_payload.get("allowed"))
    if json_mode:
        sys.stdout.write(
            f"{json.dumps({'allowed': allowed, 'governance_reload': governance_payload, 'editing_route': route_payload}, indent=2)}\n"
        )
    else:
        sys.stdout.write(f"{governance_payload['summary']}\n")
        if governance_payload.get("next_step"):
            sys.stdout.write(f"{governance_payload['next_step']}\n")
        sys.stdout.write(f"{route_payload['summary']}\n")
        if route_payload.get("next_step"):
            sys.stdout.write(f"{route_payload['next_step']}\n")
    return 0 if allowed else 1


def _helper_command_mutates_workflow(subcommand: str, args: list[str]) -> bool:
    normalized_args = {str(item or "").strip().lower() for item in list(args or [])}
    if {"--help", "-h"} & normalized_args:
        return False
    if subcommand in {
        "status",
        "inbox",
        "context",
        "use-change",
        "direct-work",
        "clear-route",
        "assert-edit-route",
        "workflow-gate",
        "batch-plan",
        "batch-status",
        "batch-inspect",
        "batch-purge-queue",
        "batch-clear-queue",
        "batch-purge-entry",
        "batch-clear-entry",
    }:
        return False
    if subcommand in {"reconcile-pr-branch", "refresh-change-branch", "publish-pr"}:
        return "--apply" in normalized_args
    if subcommand == "changes":
        nested = str((args[0] if args else "") or "").strip().lower()
        return nested not in {"list", "show"}
    return True


def _work_item_command_requests_execution(args: list[str]) -> bool:
    requested_status = (_option_value(args, "--status") or "").strip().lower().replace("-", "_")
    return requested_status in {"in_progress", "ready_for_review", "done"}


def _change_command_requests_execution(args: list[str]) -> bool:
    requested_status = (_option_value(args, "--status") or "").strip().lower().replace("-", "_")
    return requested_status in {"active", "ready_for_review", "approved", "merged"}


def _is_draft_planning_change_mutation(subcommand: str, args: list[str]) -> bool:
    if subcommand == "change":
        target_change_id = _command_target_change_id(subcommand, args)
    elif subcommand == "changes" and str((args[0] if args else "") or "").strip().lower() == "update":
        target_change_id = _command_target_change_id(subcommand, args)
    else:
        return False
    if not target_change_id or _change_command_requests_execution(args):
        return False
    return _change_status(target_change_id) == "draft"


def _is_draft_planning_work_item_mutation(subcommand: str, args: list[str]) -> bool:
    if subcommand == "work-item":
        target_change_id = _command_target_change_id(subcommand, args)
    elif subcommand == "changes" and str((args[0] if args else "") or "").strip().lower() == "work-item":
        target_change_id = _command_target_change_id(subcommand, args)
    else:
        return False
    if not target_change_id or _work_item_command_requests_execution(args):
        return False
    return _change_status(target_change_id) == "draft"


def _helper_command_needs_route_guard(subcommand: str, args: list[str]) -> bool:
    if not _helper_command_mutates_workflow(subcommand, args):
        return False
    if _is_draft_planning_change_mutation(subcommand, args):
        return False
    if _is_draft_planning_work_item_mutation(subcommand, args):
        return False
    if subcommand in {
        "start-change",
        "proposals",
        "promote-proposal",
        "close-change",
        "batch-enqueue",
        "batch-start-next",
        "batch-cancel-queue",
        "batch-cancel-entry",
        "batch-retry-entry",
        "batch-purge-queue",
        "batch-clear-queue",
        "batch-purge-entry",
        "batch-clear-entry",
    }:
        return False
    if subcommand == "changes":
        nested = str((args[0] if args else "") or "").strip().lower()
        return nested in {"update", "task", "move-task"}
    return subcommand in {"change", "task", "pickup-task", "handoff-review", "prepare-pr", "publish-pr", "deliver-change", "reconcile-pr-branch", "refresh-change-branch"}


def _helper_command_requires_governance_reload(subcommand: str, args: list[str]) -> bool:
    normalized_args = {str(item or "").strip().lower() for item in list(args or [])}
    if {"--help", "-h"} & normalized_args:
        return False
    if subcommand in {"assistant-startup", "context", "use-change", "direct-work", "clear-route", "assert-edit-route"}:
        return False
    return _helper_command_mutates_workflow(subcommand, args)


def _command_target_change_id(subcommand: str, args: list[str]) -> str | None:
    positional_args = [
        value for value in list(args or []) if str(value or "").strip() and not str(value or "").strip().startswith("-")
    ]
    if subcommand in {"change", "task", "pickup-task", "handoff-review", "prepare-pr", "publish-pr", "deliver-change", "reconcile-pr-branch", "refresh-change-branch", "close-change"}:
        change_id = str((positional_args[0] if positional_args else "") or "").strip()
        return change_id or None
    if subcommand == "changes":
        nested = str((args[0] if args else "") or "").strip().lower()
        nested_positionals = [
            value for value in list(args[1:] if args else []) if str(value or "").strip() and not str(value or "").strip().startswith("-")
        ]
        if nested in {"update", "task", "move-task"}:
            change_id = str((nested_positionals[0] if nested_positionals else "") or "").strip()
            return change_id or None
    return None


def _ensure_change_route_for_mutation(subcommand: str, args: list[str]) -> dict[str, object]:
    target_change_id = _command_target_change_id(subcommand, args)
    route_state = _load_route_state()
    current_branch = _git_current_branch()
    if (
        target_change_id
        and route_state
        and route_state.get("route_kind") == "active_change"
        and route_state.get("change_id") == target_change_id
        and route_state.get("recorded_branch_name")
        and route_state.get("recorded_branch_name") == current_branch
    ):
        return {
            "status": "active_change",
            "allowed": True,
            "change_id": target_change_id,
            "reason": None,
            "recorded_at": route_state.get("recorded_at"),
            "source": route_state.get("source"),
            "summary": f"Active change route is {target_change_id}.",
            "next_step": None,
            "current_branch": current_branch,
            "recorded_branch_name": route_state.get("recorded_branch_name"),
            "fast_path": True,
        }
    route_payload = _resolve_editing_route()
    if route_payload.get("allowed"):
        return route_payload
    current_branch = str(route_payload.get("current_branch") or _git_current_branch() or "").strip() or None
    branch_change_candidates = route_payload.get("branch_change_candidates")
    if not isinstance(branch_change_candidates, list):
        branch_change_candidates = _changes_bound_to_branch(current_branch)
    if target_change_id and _change_exists(target_change_id):
        healed_payload = _attempt_route_self_heal(
            route_payload,
            source="helper:auto-heal-target",
            explicit_change_id=target_change_id,
            action=f"mutating {target_change_id}",
        )
        if healed_payload is not None:
            if healed_payload.get("allowed"):
                return healed_payload
            if healed_payload.get("auto_heal_attempted"):
                return healed_payload
        target_branch_name = _bound_branch_for_change(target_change_id)
        if not target_branch_name or (current_branch and target_branch_name == current_branch):
            _set_active_change_route(target_change_id, source="helper:auto-reconcile-target")
            reconciled_payload = _resolve_editing_route()
            reconciled_payload["auto_reconciled"] = True
            reconciled_payload["reconciled_from_change_id"] = route_payload.get("change_id")
            reconciled_payload["reconciled_to_change_id"] = target_change_id
            reconciled_payload["summary"] = (
                f"Auto-reconciled the active change route to {target_change_id} from the explicit helper target."
            )
            return reconciled_payload
        if len(branch_change_candidates) == 1:
            branch_change_id = str(branch_change_candidates[0] or "").strip() or None
            if branch_change_id == target_change_id:
                _set_active_change_route(target_change_id, source="helper:auto-reconcile-target")
                reconciled_payload = _resolve_editing_route()
                reconciled_payload["auto_reconciled"] = True
                reconciled_payload["reconciled_from_change_id"] = route_payload.get("change_id")
                reconciled_payload["reconciled_to_change_id"] = target_change_id
                reconciled_payload["summary"] = (
                    f"Auto-reconciled the active change route to {target_change_id} because the current branch {current_branch} is bound to that change."
                )
                return reconciled_payload
            return {
                **route_payload,
                "status": "blocked_branch_route_target_mismatch",
                "allowed": False,
                "branch_change_id": branch_change_id,
                "branch_change_candidates": branch_change_candidates,
                "summary": (
                    f"Current branch {current_branch} is bound to {branch_change_id}, but this helper command targets {target_change_id}."
                ),
                "next_step": (
                    f"Switch to the branch bound to {target_change_id} before mutating it, or target {branch_change_id} while staying on `{current_branch}`."
                ),
            }
        return {
            **route_payload,
            "status": "blocked_branch_route_target_mismatch",
            "allowed": False,
            "summary": (
                f"This helper command targets {target_change_id}, but the current branch {current_branch or 'unknown'} does not match that change's bound branch."
            ),
            "next_step": f"Switch to `{target_branch_name}` before mutating {target_change_id}.",
        }
    if len(branch_change_candidates) != 1:
        return route_payload
    branch_change_id = str(branch_change_candidates[0] or "").strip() or None
    if not branch_change_id:
        return route_payload
    _set_active_change_route(branch_change_id, source="helper:auto-reconcile-branch")
    reconciled_payload = _resolve_editing_route()
    reconciled_payload["auto_reconciled"] = True
    reconciled_payload["reconciled_from_change_id"] = route_payload.get("change_id")
    reconciled_payload["reconciled_to_change_id"] = branch_change_id
    reconciled_payload["summary"] = (
        f"Auto-reconciled the active change route to {branch_change_id} because the current branch {current_branch} is bound to that change."
    )
    return reconciled_payload


def _workflow_command(subcommand: str, args: list[str]) -> int:
    json_mode = _json_mode_requested(args)
    try:
        if subcommand == "context":
            return _context_with_route(args)
        if _helper_command_requires_governance_reload(subcommand, args):
            governance_payload = _governance_reload_gate_payload()
            if not governance_payload.get("allowed"):
                summary = str(governance_payload.get("summary") or "Assistant governance reload is blocked.")
                next_step = str(governance_payload.get("next_step") or "").strip()
                if json_mode:
                    details: dict[str, object] = {
                        "governance_reload": governance_payload,
                    }
                    if next_step:
                        details["next_step"] = next_step
                    return _emit_helper_json_error("governance_reload_blocked", summary, details=details, returncode=1)
                print(summary, file=sys.stderr)
                if next_step:
                    print(next_step, file=sys.stderr)
                return 1
        if _load_service_mode().get("enabled") and _helper_command_mutates_workflow(subcommand, args):
            message = (
                f"{_service_mode_gate_detail()} Repo-local workflow mutations are blocked until service mode is disabled in Global settings."
            )
            if json_mode:
                return _emit_helper_json_error("service_mode_active", message, returncode=1)
            print(message, file=sys.stderr)
            return 1
        if _helper_command_needs_route_guard(subcommand, args):
            route_payload = _ensure_change_route_for_mutation(subcommand, args)
            if not route_payload.get("allowed"):
                summary = str(route_payload.get("summary") or "The repo-local edit route is blocked.")
                next_step = str(route_payload.get("next_step") or "").strip()
                if json_mode:
                    details = {
                        "route": route_payload,
                    }
                    if next_step:
                        details["next_step"] = next_step
                    return _emit_helper_json_error("edit_route_blocked", summary, details=details, returncode=1)
                print(summary, file=sys.stderr)
                if next_step:
                    print(next_step, file=sys.stderr)
                return 1
            if route_payload.get("auto_reconciled") and not json_mode:
                print(str(route_payload.get("summary") or "Auto-reconciled the repo-local route."), file=sys.stderr)
        result = _run_underlying_verlyn(
            subcommand,
            args,
            emit_output=not json_mode,
            capture_output=not _should_stream_underlying_output(subcommand, args),
        )
    except RuntimeError as exc:
        if json_mode:
            return _emit_helper_json_error("verlyn_cli_unavailable", str(exc), returncode=1)
        print(str(exc), file=sys.stderr)
        return 1
    try:
        _record_route_after_command(subcommand, args, result)
    except AssistantRouteStateError as exc:
        summary = str(exc).strip()
        if json_mode:
            details = _route_state_error_details(exc)
            details["subcommand"] = subcommand
            details["args"] = list(args or [])
            return _emit_helper_json_error(
                "edit_route_persistence_failed",
                summary,
                details=details,
                returncode=1,
            )
        print(f"Error: {summary}", file=sys.stderr)
        return 1
    if json_mode:
        stdout_text = str(result.stdout or "")
        if result.returncode == 0:
            if stdout_text:
                sys.stdout.write(stdout_text if stdout_text.endswith("\n") else f"{stdout_text}\n")
            return 0
        try:
            json.loads(stdout_text or "{}")
        except Exception:
            details = {
                "subcommand": subcommand,
                "args": list(args or []),
            }
            stderr_text = str(result.stderr or "").strip()
            if stderr_text:
                details["stderr"] = stderr_text
            if stdout_text.strip():
                details["stdout"] = stdout_text.strip()
            return _emit_helper_json_error(
                "underlying_command_failed",
                stderr_text or stdout_text.strip() or "Underlying Verlyn command failed.",
                details=details,
                returncode=int(result.returncode),
            )
        if stdout_text:
            sys.stdout.write(stdout_text if stdout_text.endswith("\n") else f"{stdout_text}\n")
        return int(result.returncode)
    return int(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repo-local mode helper for this repo. Wraps the Verlyn workflow path without making you leave the target repo."
    )
    parser.add_argument(
        "command",
        choices=[
            "status",
            "inbox",
            "start-change",
            "pickup-task",
            "pickup-work-item",
            "batch-plan",
            "batch-enqueue",
            "batch-status",
            "batch-inspect",
            "batch-start-next",
            "batch-cancel-queue",
            "batch-cancel-entry",
            "batch-retry-entry",
            "batch-purge-queue",
            "batch-clear-queue",
            "batch-purge-entry",
            "batch-clear-entry",
            "use-change",
            "direct-work",
            "clear-route",
            "assistant-startup",
            "assert-edit-route",
            "change",
            "task",
            "work-item",
            "handoff-review",
            "prepare-pr",
            "publish-pr",
            "deliver-change",
            "refresh-change-branch",
            "reconcile-pr-branch",
            "close-change",
            "context",
            "changes",
            "proposals",
            "work-item-proposals",
            "promote-proposal",
            "promote-work-item-proposal",
            "workflow-gate",
        ],
        help="Workflow helper command to run for this repo.",
    )
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments forwarded to the wrapped Verlyn command.")
    parsed = parser.parse_args()
    forwarded = list(parsed.args or [])
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]
    explicit_operator, forwarded = _strip_explicit_assistant_operator_args(forwarded)
    if explicit_operator:
        os.environ["VERLYN_ASSISTANT_OPERATOR"] = explicit_operator
    command, forwarded = _normalize_helper_command(parsed.command, forwarded)
    if any(str(item or "").strip().lower() in {"--help", "-h"} for item in forwarded):
        if command == "use-change":
            print("usage: verlyn_workflow.py use-change CHANGE_ID")
            print("Route this repo-local assistant session to an existing change.")
            return 0
        if command == "direct-work":
            print("usage: verlyn_workflow.py direct-work --reason REASON")
            print("Record an explicit direct-work exception for this repo-local session.")
            return 0
        if command == "clear-route":
            print("usage: verlyn_workflow.py clear-route")
            print("Clear the repo-local assistant edit route.")
            return 0
    if command == "use-change":
        return _cmd_use_change(forwarded)
    if command == "direct-work":
        return _cmd_direct_work(forwarded)
    if command == "clear-route":
        return _cmd_clear_route()
    if command == "assistant-startup":
        return _cmd_assistant_startup(forwarded)
    if command == "assert-edit-route":
        return _cmd_assert_edit_route(forwarded)
    return _workflow_command(command, forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
