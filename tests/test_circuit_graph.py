from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.assembly_plans import create_router
from backend.api.dependencies import ApiDependencies
from backend.services.circuit_graph_ai import CircuitGraphAiEnrichmentService, normalize_circuit_graph_enrichment
from backend.services.circuit_graph import build_circuit_graph


def sample_plan() -> dict:
    return {
        "id": "plan-1",
        "title": "NE555 LED flasher",
        "objective": "Build a 555 timer LED flasher.",
        "componentName": "NE555",
        "componentType": "timer",
        "summary": "Blink an LED from a timer output.",
        "confidence": 0.82,
        "status": "active",
        "parts": [
            {"id": "part-1", "name": "NE555 timer IC", "detail": "DIP package"},
            {"id": "part-2", "name": "LED", "detail": "indicator"},
            {"id": "part-3", "name": "330 ohm resistor", "detail": "LED current limit"},
        ],
        "power": [{"id": "power-1", "note": "Use a regulated 5V supply and common ground."}],
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
                "note": "Power the timer.",
                "sourcePath": "ne555.pdf",
                "page": 3,
            },
            {
                "id": "step-3",
                "ordinal": 3,
                "type": "wiring",
                "title": "NE555 pin 3 OUT",
                "instruction": "LED anode",
                "note": "Drive the LED through the resistor.",
                "sourcePath": "ne555.pdf",
                "page": 3,
            },
        ],
        "sources": [{"sourcePath": "ne555.pdf", "displayName": "NE555 datasheet", "pages": [3]}],
        "notes": [],
    }


def test_build_circuit_graph_preserves_pins_nets_and_evidence():
    graph = build_circuit_graph(sample_plan())

    assert graph["schemaVersion"] == 1
    assert graph["planId"] == "plan-1"
    assert graph["stats"]["connectionCount"] == 3
    assert any(pin["pinNumber"] == "1" and pin["function"] == "ground" for pin in graph["pins"])
    assert any(net["role"] == "ground" and net["name"] == "GND" for net in graph["nets"])
    assert any(net["role"] == "power" for net in graph["nets"])
    assert graph["connections"][0]["evidence"]["sourcePath"] == "ne555.pdf"
    assert graph["connections"][0]["evidence"]["page"] == 3


def test_build_circuit_graph_blocks_export_when_pin_evidence_is_missing():
    plan = sample_plan()
    plan["steps"] = [
        {
            "id": "step-1",
            "ordinal": 1,
            "type": "wiring",
            "title": "Timer output",
            "instruction": "LED",
            "note": "No pin number provided.",
        }
    ]

    graph = build_circuit_graph(plan)

    assert graph["status"] == "needs_evidence"
    assert any(item["code"] == "pin_number_missing" for item in graph["validationFindings"])


def test_circuit_graph_endpoint_returns_graph_for_owned_plan():
    plan = sample_plan()

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

    response = TestClient(app).get("/api/assembly-plans/plan-1/circuit-graph")

    assert response.status_code == 200
    body = response.json()
    assert body["graph"]["planId"] == "plan-1"
    assert body["graph"]["stats"]["pinCount"] >= 3


def test_circuit_graph_ai_enrichment_records_local_usage_without_openai():
    events = []

    class Store:
        def record_ai_assist_event(self, **kwargs):
            events.append(kwargs)

    class OpenAi:
        def enrich_circuit_graph(self, **kwargs):
            raise AssertionError("OpenAI should not run for high-confidence local enrichment")

    def local_llm(_prompt, _model, **kwargs):
        assert kwargs["gpu_resource_class"] == "local_llm"
        return (
            '{"useful":true,"confidence":0.91,"summary":"graph is usable",'
            '"proposedPins":[],"proposedNets":[],"proposedConnections":[],'
            '"validationFindings":[],"escalateToOpenAI":false,"reason":"grounded"}'
        )

    service = CircuitGraphAiEnrichmentService(
        ai_provider_store=Store(),
        openai_assist_service=OpenAi(),
        query_local_llm=local_llm,
        local_model_name="electronics-helper",
    )

    result = service.enrich(plan=sample_plan(), graph=build_circuit_graph(sample_plan()), entity_id=5, user_id=7)

    assert result["provider"] == "ollama"
    assert result["escalated"] is False
    assert result["local"]["confidence"] == 0.91
    assert events[0]["provider"] == "ollama"
    assert events[0]["task_type"] == "circuit_graph"
    assert events[0]["context_type"] == "assembly_plan"
    assert events[0]["paid_by"] == "entity"


def test_circuit_graph_ai_enrichment_escalates_after_low_confidence_local_review():
    class Store:
        def record_ai_assist_event(self, **_kwargs):
            pass

    class OpenAi:
        def __init__(self):
            self.calls = []

        def enrich_circuit_graph(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "provider": "openai",
                "model": "gpt-5-chat-latest",
                "useful": True,
                "confidence": 0.72,
                "summary": "needs manual pin review",
                "validationFindings": [{"severity": "blocking", "message": "pin evidence missing"}],
                "escalateToOpenAI": False,
                "reason": "cloud review completed",
            }

    def local_llm(_prompt, _model, **_kwargs):
        return (
            '{"useful":true,"confidence":0.31,"summary":"ambiguous",'
            '"proposedPins":[],"proposedNets":[],"proposedConnections":[],'
            '"validationFindings":["pin evidence missing"],'
            '"escalateToOpenAI":true,"reason":"local evidence is ambiguous"}'
        )

    openai = OpenAi()
    service = CircuitGraphAiEnrichmentService(
        ai_provider_store=Store(),
        openai_assist_service=openai,
        query_local_llm=local_llm,
        local_model_name="electronics-helper",
    )

    result = service.enrich(plan=sample_plan(), graph=build_circuit_graph(sample_plan()), entity_id=None, user_id=7)

    assert result["provider"] == "ollama+openai"
    assert result["escalated"] is True
    assert len(openai.calls) == 1
    assert openai.calls[0]["enabled"] is True
    assert result["openai"]["provider"] == "openai"


def test_normalize_circuit_graph_enrichment_clamps_shape():
    normalized = normalize_circuit_graph_enrichment(
        {
            "confidence": 5,
            "proposedPins": ["bad", {"componentId": "u1"}],
            "validationFindings": ["review pinout"],
        }
    )

    assert normalized["confidence"] == 1.0
    assert normalized["proposedPins"] == [{"componentId": "u1"}]
    assert normalized["validationFindings"] == [
        {"severity": "warning", "code": "ai_review", "message": "review pinout"}
    ]
