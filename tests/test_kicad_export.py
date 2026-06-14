from __future__ import annotations

import base64
import zipfile
from io import BytesIO
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.assembly_plans import create_router
from backend.api.dependencies import ApiDependencies
from backend.services.circuit_graph import build_circuit_graph
from backend.services.kicad_export import build_kicad_project_package


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
            {
                "id": "step-1",
                "ordinal": 1,
                "type": "wiring",
                "title": "Pin 1 GND",
                "instruction": "Ground rail",
                "note": "Common ground",
                "sourcePath": "ne555.pdf",
                "page": 3,
            },
            {
                "id": "step-2",
                "ordinal": 2,
                "type": "wiring",
                "title": "Pin 8 VCC",
                "instruction": "5V positive rail",
                "note": "Power input",
                "sourcePath": "ne555.pdf",
                "page": 3,
            },
        ],
        "sources": [{"sourcePath": "ne555.pdf", "displayName": "NE555 datasheet", "pages": [3]}],
        "notes": [],
    }


def test_kicad_package_contains_deterministic_project_files():
    plan = exportable_plan()
    graph = build_circuit_graph(plan)

    package = build_kicad_project_package(plan, graph)
    second = build_kicad_project_package(plan, graph)

    assert package["exportable"] is True
    assert package["projectName"] == "ne555-rail-check"
    assert package["zipBase64"] == second["zipBase64"]
    paths = {item["path"] for item in package["files"]}
    assert paths == {
        "ne555-rail-check.kicad_pro",
        "ne555-rail-check.kicad_sch",
        "circuit-graph.json",
        "README.md",
        "manifest.json",
    }
    schematic = next(item["content"] for item in package["files"] if item["path"].endswith(".kicad_sch"))
    assert "(kicad_sch" in schematic
    assert "Connections:" in schematic
    with zipfile.ZipFile(BytesIO(base64.b64decode(package["zipBase64"]))) as archive:
        assert sorted(archive.namelist()) == sorted(paths)


def test_kicad_package_blocks_when_graph_needs_evidence():
    plan = exportable_plan()
    plan["steps"][0]["title"] = "Timer ground"
    graph = build_circuit_graph(plan)

    package = build_kicad_project_package(plan, graph)

    assert package["exportable"] is False
    assert package["files"] == []
    assert package["zipBase64"] == ""
    assert any(item["code"] == "connection_without_pin" for item in package["validation"]["blocking"])


def test_kicad_project_endpoint_returns_package_for_owned_plan():
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

    response = TestClient(app).get("/api/assembly-plans/plan-1/kicad-project")

    assert response.status_code == 200
    package = response.json()["package"]
    assert package["exportable"] is True
    assert package["manifest"]["projectName"] == "ne555-rail-check"
