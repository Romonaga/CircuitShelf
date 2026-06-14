from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.services.fabrication_export as fabrication_export
from backend.api.assembly_plans import create_router
from backend.api.dependencies import ApiDependencies
from backend.services.circuit_graph import build_circuit_graph
from backend.services.fabrication_export import build_fabrication_package


def exportable_plan() -> dict:
    return {
        "id": "plan-1",
        "title": "NE555 Rail Check",
        "objective": "Wire 555 power rails.",
        "componentName": "NE555",
        "componentType": "timer",
        "summary": "Wire power and ground.",
        "confidence": 0.84,
        "status": "active",
        "parts": [{"id": "part-1", "name": "NE555 timer IC", "detail": "DIP"}],
        "power": [{"id": "power-1", "note": "Use regulated 5V and common ground."}],
        "steps": [
            {"id": "step-1", "ordinal": 1, "type": "wiring", "title": "Pin 1 GND", "instruction": "Ground rail", "note": "Ground"},
            {"id": "step-2", "ordinal": 2, "type": "wiring", "title": "Pin 8 VCC", "instruction": "5V positive rail", "note": "Power"},
        ],
        "sources": [],
        "notes": [],
    }


def fake_kicad_package():
    return {
        "exportable": True,
        "projectName": "fake-project",
        "manifest": {"projectName": "fake-project"},
        "files": [
            {"path": "fake-project.kicad_pro", "mimeType": "application/json", "content": "{}"},
            {"path": "fake-project.kicad_pcb", "mimeType": "text/plain", "content": "(kicad_pcb)"},
        ],
        "zipBase64": "ZmFrZQ==",
        "validation": {"blocking": [], "warnings": []},
    }


def test_fabrication_package_needs_layout_when_project_has_no_pcb():
    plan = exportable_plan()
    graph = build_circuit_graph(plan)

    package = build_fabrication_package(plan, graph)

    assert package["generated"] is False
    assert package["status"] == "needs_layout"
    assert package["manifest"]["checks"][0]["code"] == "pcb_layout_missing"


def test_fabrication_package_runs_kicad_cli_and_collects_outputs(monkeypatch):
    monkeypatch.setattr(fabrication_export, "build_kicad_project_package", lambda _plan, _graph: fake_kicad_package())

    def runner(command: list[str], _project_dir: Path, output_dir: Path):
        if "gerbers" in command:
            (output_dir / "fake-F_Cu.gbr").write_text("G04 copper*", encoding="utf-8")
        if "drill" in command:
            (output_dir / "fake.drl").write_text("M48", encoding="utf-8")

    package = build_fabrication_package(exportable_plan(), build_circuit_graph(exportable_plan()), kicad_cli_path="/usr/bin/kicad-cli", runner=runner)

    assert package["generated"] is True
    assert package["status"] == "generated"
    assert {item["kind"] for item in package["files"]} == {"gerber", "drill"}
    assert package["manifest"]["checks"][0]["code"] == "fabrication_files_generated"


def test_fabrication_package_reports_kicad_cli_failure(monkeypatch):
    monkeypatch.setattr(fabrication_export, "build_kicad_project_package", lambda _plan, _graph: fake_kicad_package())

    def runner(_command: list[str], _project_dir: Path, _output_dir: Path):
        raise RuntimeError("bad board")

    package = build_fabrication_package(exportable_plan(), build_circuit_graph(exportable_plan()), kicad_cli_path="/usr/bin/kicad-cli", runner=runner)

    assert package["generated"] is False
    assert package["status"] == "failed"
    assert package["manifest"]["checks"][0]["code"] == "kicad_cli_failed"


def test_fabrication_endpoint_returns_preflight_package_for_owned_plan():
    plan = exportable_plan()

    class Store:
        def get(self, plan_id: str, user_id: int | None = None):
            assert user_id == 7
            return plan if plan_id == "plan-1" else None

    deps = ApiDependencies(
        require_authenticated_user=lambda req: (SimpleNamespace(username="tester", id=7), None),
        require_entity_member=lambda req: (None, None, None),
        require_entity_admin=lambda req: (None, None, None),
        require_system_admin_user=lambda req: (None, None),
        bearer_token_from_request=lambda req: "",
        session_timeout_seconds=lambda: 300,
        user_payload=lambda user: {},
        user_id_for_user=lambda user: user.id,
        verify_user=lambda username, password: None,
        user_store=None,
        user_preferences_store=None,
        account_profile_store=None,
        entity_store=None,
        password_policy_store=None,
        ai_provider_store=None,
    )
    app = FastAPI()
    app.include_router(
        create_router(
            deps,
            assembly_plan_store=Store(),
            conversation_store=None,
            bench_tools=SimpleNamespace(build_assembly_export=lambda plan, format: {}),
            openai_assist_service=None,
            get_rag_response=lambda **kwargs: None,
            query_ollama_chat_with_retry=lambda *args, **kwargs: None,
            normalize_sources_for_api=lambda sources: sources,
            build_recovery_prompt=lambda question, answer, sources: "",
            parse_recovered_build_card=lambda raw, sources: None,
            recovery_system_prompt="",
            default_model="local",
            username_for_user=lambda user: user.username,
        )
    )

    response = TestClient(app).get("/api/assembly-plans/plan-1/fabrication-package")

    assert response.status_code == 422
    package = response.json()["package"]
    assert package["status"] == "needs_layout"
