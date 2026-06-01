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

    monkeypatch.setattr(service, "_create_response", fail_create_response)

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
