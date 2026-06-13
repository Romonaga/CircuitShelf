from __future__ import annotations

from backend.services.openai_assist_service import OpenAIAssistService


class BudgetBlockedStore:
    def __init__(self):
        self.events = []

    def resolve_openai_assist(self, *, entity_id, user_id):
        return {
            "apiKey": "sk-test",
            "assistMode": "auto",
            "modelName": "gpt-5-chat-latest",
            "paidBy": "entity",
            "providerKeyOwnerUserId": None,
            "pricingScope": "entity",
            "pricingEntityId": entity_id,
            "pricingUserId": None,
            "monthlyBudget": 5.0,
            "warnPercent": 80,
            "stopPercent": 100,
        }

    def budget_status_for_settings(self, settings):
        return {
            "monthlyBudget": 5.0,
            "monthSpend": 5.25,
            "warnAt": 4.0,
            "stopAt": 5.0,
            "warned": True,
            "blocked": True,
        }

    def record_ai_assist_event(self, **kwargs):
        self.events.append(kwargs)
        return 1


def test_answer_without_sources_blocks_when_budget_exceeded(monkeypatch):
    store = BudgetBlockedStore()
    service = OpenAIAssistService(store)

    def fail_create_response(**_kwargs):
        raise AssertionError("OpenAI should not be called when budget is blocked")

    monkeypatch.setattr(service.tasks, "_create_response", fail_create_response)

    result = service.answer_without_sources(
        question="What is a 555 timer?",
        entity_id=7,
        user_id=3,
        context_type="conversation",
        context_id=None,
    )

    assert result is None
    assert len(store.events) == 1
    assert store.events[0]["success"] is False
    assert "budget exceeded" in store.events[0]["error_message"]


class IngestionAssistStore:
    def __init__(self):
        self.events = []
        self.reviews = []
        self.resolved = None

    def resolve_openai_ingestion_assist(self, *, is_global, entity_id, user_id):
        self.resolved = {"is_global": is_global, "entity_id": entity_id, "user_id": user_id}
        return {
            "apiKey": "sk-test",
            "assistMode": "auto",
            "modelName": "gpt-5-chat-latest",
            "paidBy": "system" if is_global else "entity",
            "providerKeyOwnerUserId": None,
            "pricingScope": "system" if is_global else "entity",
            "pricingEntityId": None if is_global else entity_id,
            "pricingUserId": None,
            "monthlyBudget": 0,
            "warnPercent": 80,
            "stopPercent": 100,
        }

    def resolve_openai_assist(self, *, entity_id, user_id):
        self.resolved = {"is_global": False, "entity_id": entity_id, "user_id": user_id}
        return {
            "apiKey": "sk-test",
            "assistMode": "auto",
            "modelName": "gpt-5-chat-latest",
            "paidBy": "entity",
            "providerKeyOwnerUserId": None,
            "pricingScope": "entity",
            "pricingEntityId": entity_id,
            "pricingUserId": None,
            "monthlyBudget": 0,
            "warnPercent": 80,
            "stopPercent": 100,
        }

    def budget_status_for_settings(self, _settings):
        return {"blocked": False}

    def estimate_cost(self, **_kwargs):
        return 0.0123

    def record_ai_assist_event(self, **kwargs):
        self.events.append(kwargs)
        return 1

    def record_document_ingest_ai_review(self, **kwargs):
        self.reviews.append(kwargs)
        return 1


def test_ingestion_review_uses_scoped_provider_and_records_cost(monkeypatch):
    store = IngestionAssistStore()
    service = OpenAIAssistService(store)

    monkeypatch.setattr(
        service.tasks,
        "_create_response",
        lambda **_kwargs: {
            "output_text": '{"quality":"good","useful":true,"warnings":[],"suggestedReviewFocus":"pinouts"}',
            "usage": {"input_tokens": 100, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 5}},
        },
    )

    result = service.review_ingestion(
        source_path="555.pdf",
        is_global=True,
        entity_id=None,
        user_id=7,
        stats={"chunkCount": 10},
        sample_text="555 timer pinout text",
        enabled=True,
    )

    assert result is not None
    assert result["paidBy"] == "system"
    assert store.resolved == {"is_global": True, "entity_id": None, "user_id": 7}
    assert store.events[0]["task_type"] == "ingestion_assist"
    assert store.events[0]["estimated_cost"] == 0.0123
    assert store.reviews[0]["source_path"] == "555.pdf"
    assert store.reviews[0]["review_json"]["quality"] == "good"


def test_datasheet_repair_records_usage_and_structured_review(monkeypatch):
    store = IngestionAssistStore()
    service = OpenAIAssistService(store)

    monkeypatch.setattr(
        service.tasks,
        "_create_response",
        lambda **_kwargs: {
            "output_text": (
                '{"componentName":"LM555","componentType":"timer","confidence":0.92,'
                '"facts":[{"type":"voltage","label":"VCC","value":"5 to 15","unit":"V","page":5,"evidence":"VCC 5 V to 15 V"}],'
                '"pinout":{"pins":[{"pin":1,"label":"GND","function":"Ground","page":3,"evidence":"Pin 1 GND"}]},'
                '"notes":[]}'
            ),
            "usage": {"input_tokens": 200, "output_tokens": 50, "input_tokens_details": {"cached_tokens": 10}},
        },
    )

    result = service.repair_datasheet_intelligence(
        source_path="lm555.pdf",
        is_global=False,
        entity_id=4,
        user_id=7,
        local_intelligence={"componentName": "LM555", "componentType": "timer", "confidence": 0.7, "facts": [], "pinout": {"pins": []}},
        sample_text="LM555 pin functions page text",
        enabled=True,
    )

    assert result is not None
    assert result["repair"]["componentName"] == "LM555"
    assert store.resolved == {"is_global": False, "entity_id": 4, "user_id": 7}
    assert store.events[0]["task_type"] == "ingestion_assist"
    assert store.events[0]["context_type"] == "datasheet_intelligence"
    assert store.events[0]["estimated_cost"] == 0.0123
    assert store.reviews[0]["review_json"]["kind"] == "datasheet_intelligence_repair"


def test_project_finder_triage_records_project_finder_usage(monkeypatch):
    store = IngestionAssistStore()
    service = OpenAIAssistService(store)

    monkeypatch.setattr(
        service.tasks,
        "_create_response",
        lambda **_kwargs: {
            "output_text": (
                '{"candidates":[{"id":"candidate-1","useful":true,"confidence":0.82,'
                '"recommendedAction":"keep","notes":[],"escalateToOpenAI":false,'
                '"reason":"candidate is grounded"}]}'
            ),
            "usage": {"input_tokens": 120, "output_tokens": 30, "input_tokens_details": {"cached_tokens": 4}},
        },
    )

    result = service.triage_project_finder(
        candidates=[{"id": "candidate-1", "summary": "555 timer project", "score": 42}],
        entity_id=4,
        user_id=7,
        enabled=True,
        decision_reason="local Project Finder triage requested OpenAI escalation",
    )

    assert result["candidates"][0]["id"] == "candidate-1"
    assert result["estimatedCost"] == 0.0123
    assert store.events[0]["task_type"] == "project_finder"
    assert store.events[0]["context_type"] == "project_finder"
    assert store.events[0]["estimated_cost"] == 0.0123


def test_bench_photo_verification_records_photo_check_usage(monkeypatch):
    store = IngestionAssistStore()
    service = OpenAIAssistService(store)

    monkeypatch.setattr(
        service.tasks,
        "_create_multimodal_response",
        lambda **_kwargs: {
            "output_text": (
                '{"status":"needs_attention","confidence":0.64,"summary":"jumper is unclear",'
                '"findings":["jumper end is hidden"],"requestedEvidence":["close-up of row 12"]}'
            ),
            "usage": {"input_tokens": 150, "output_tokens": 35, "input_tokens_details": {"cached_tokens": 5}},
        },
    )

    result = service.verify_bench_photo(
        image_bytes=b"fake-image",
        mime_type="image/png",
        plan={"title": "LED plan", "objective": "blink LED"},
        step={"ordinal": 1, "title": "LED", "instruction": "connect LED"},
        note="check step",
        diagnostics={"width": 1200, "height": 900},
        local_review={"status": "cannot_verify"},
        entity_id=4,
        user_id=7,
        enabled=True,
        decision_reason="local requested vision escalation",
    )

    assert result["status"] == "needs_attention"
    assert result["estimatedCost"] == 0.0123
    assert store.events[0]["task_type"] == "photo_check"
    assert store.events[0]["context_type"] == "bench_photo_verification"
    assert store.events[0]["estimated_cost"] == 0.0123
