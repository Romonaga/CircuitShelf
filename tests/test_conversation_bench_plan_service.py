from __future__ import annotations

from backend.services.conversation_bench_plan_service import ConversationBenchPlanService, extract_source_payload


def conversation_with_snapshot(build_card=None):
    snapshot = {
        "sources": [
            {
                "source": "training/ne555.pdf",
                "displayName": "NE555 datasheet",
                "pages": [3],
                "chunkCount": 2,
                "chunks": [{"page": 3, "section": "Pinout", "preview": "Pin 1 GND, pin 8 VCC"}],
            }
        ],
        "buildCard": build_card,
    }
    return {
        "id": "conv-1",
        "title": "555 timer project",
        "turns": [
            {
                "id": "turn-1",
                "ordinal": 1,
                "question": "Build a 555 LED flasher",
                "answer": "Use the 555 output to drive an LED.",
                "confidence": 0.82,
                "responseSnapshot": snapshot,
            }
        ],
    }


def valid_card():
    return {
        "title": "555 LED flasher",
        "componentName": "NE555",
        "componentType": "timer",
        "summary": "Blink an LED with a 555 timer.",
        "confidence": 0.78,
        "parts": [{"name": "NE555 timer IC", "detail": "DIP package"}],
        "power": ["Use a regulated 5V supply."],
        "wiring": [
            {"from": "Pin 1 GND", "to": "Ground rail", "note": "Common ground", "page": 3},
            {"from": "Pin 8 VCC", "to": "5V rail", "note": "Power input", "page": 3},
        ],
        "checks": ["Verify polarity."],
        "warnings": ["Confirm datasheet pinout."],
        "sourceNotes": [{"source": "training/ne555.pdf", "pages": [3], "chunks": 2}],
    }


class ConversationStore:
    def __init__(self, conversation):
        self.conversation = conversation

    def get(self, conversation_id, user_id):
        assert conversation_id == "conv-1"
        assert user_id == 7
        return self.conversation


class AssemblyStore:
    def __init__(self):
        self.created = []

    def create_from_card(self, **kwargs):
        self.created.append(kwargs)
        return {"id": "plan-1", "title": kwargs["card"]["title"], "parts": [], "steps": []}


class AiStore:
    def __init__(self):
        self.events = []

    def record_ai_assist_event(self, **kwargs):
        self.events.append(kwargs)


class OpenAi:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def synthesize_conversation_bench_plan(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def make_service(conversation, *, local_response=None, openai=None, ai_store=None):
    assembly_store = AssemblyStore()
    ai_store = ai_store or AiStore()

    def local_llm(_prompt, _model, **kwargs):
        assert kwargs["gpu_resource_class"] == "local_llm"
        return local_response or "{}"

    return (
        ConversationBenchPlanService(
            conversation_store=ConversationStore(conversation),
            assembly_plan_store=assembly_store,
            ai_provider_store=ai_store,
            openai_assist_service=openai,
            query_local_llm=local_llm if local_response is not None else None,
            local_model_name="electronics-helper",
        ),
        assembly_store,
        ai_store,
    )


def test_extract_source_payload_dedupes_snapshot_sources():
    payload = extract_source_payload(conversation_with_snapshot(valid_card()))

    assert payload[0]["source"] == "training/ne555.pdf"
    assert payload[0]["pages"] == [3]
    assert payload[0]["chunkCount"] == 2
    assert payload[0]["chunks"][0]["section"] == "Pinout"


def test_conversation_build_card_snapshot_creates_plan_without_ai():
    service, assembly_store, ai_store = make_service(conversation_with_snapshot(valid_card()))

    result = service.create_plan(
        conversation_id="conv-1",
        user_id=7,
        username="tester",
        entity_id=5,
    )

    assert result["ok"] is True
    assert result["source"] == "conversation_build_card"
    assert assembly_store.created[0]["card"]["componentName"] == "NE555"
    assert ai_store.events == []


def test_local_ai_synthesis_creates_plan_and_records_usage():
    service, assembly_store, ai_store = make_service(
        conversation_with_snapshot(build_card=None),
        local_response=(
            '{"title":"555 LED flasher","componentName":"NE555","componentType":"timer",'
            '"summary":"Blink an LED.","confidence":0.74,'
            '"parts":[{"name":"NE555 timer IC","detail":"DIP"}],'
            '"power":["Use 5V."],'
            '"wiring":[{"from":"Pin 1 GND","to":"Ground rail","note":"Common ground","page":3},'
            '{"from":"Pin 8 VCC","to":"5V rail","note":"Power","page":3}],'
            '"checks":["Verify polarity"],"warnings":["Confirm pinout"],'
            '"sourceNotes":[{"source":"training/ne555.pdf","pages":[3],"chunks":2}],'
            '"useful":true,"escalateToOpenAI":false,"reason":"grounded"}'
        ),
    )

    result = service.create_plan(
        conversation_id="conv-1",
        user_id=7,
        username="tester",
        entity_id=5,
    )

    assert result["ok"] is True
    assert result["source"] == "local_ai"
    assert assembly_store.created[0]["card"]["componentName"] == "NE555"
    assert "Generated from Ask conversation" in " ".join(assembly_store.created[0]["card"]["warnings"])
    assert ai_store.events[0]["provider"] == "ollama"
    assert ai_store.events[0]["task_type"] == "assembly_plan"
    assert ai_store.events[0]["context_type"] == "conversation_to_bench"


def test_low_evidence_conversation_is_rejected_without_openai_request():
    service, assembly_store, _ai_store = make_service(
        conversation_with_snapshot(build_card=None),
        local_response='{"useful":false,"confidence":0.2,"reason":"not enough wiring","escalateToOpenAI":false}',
    )

    result = service.create_plan(
        conversation_id="conv-1",
        user_id=7,
        username="tester",
        entity_id=5,
    )

    assert result["ok"] is False
    assert result["status"] == 422
    assert assembly_store.created == []
    assert result["validation"]["issues"] == ["bench_plan_not_grounded"]


def test_openai_escalation_runs_after_low_confidence_local_review():
    openai = OpenAi(result={**valid_card(), "provider": "openai", "model": "gpt-5-chat-latest", "useful": True})
    service, assembly_store, _ai_store = make_service(
        conversation_with_snapshot(build_card=None),
        local_response='{"useful":true,"confidence":0.31,"reason":"ambiguous","escalateToOpenAI":true}',
        openai=openai,
    )

    result = service.create_plan(
        conversation_id="conv-1",
        user_id=7,
        username="tester",
        entity_id=None,
    )

    assert result["ok"] is True
    assert result["source"] == "openai"
    assert len(openai.calls) == 1
    assert openai.calls[0]["enabled"] is True
    assert assembly_store.created[0]["card"]["componentName"] == "NE555"
