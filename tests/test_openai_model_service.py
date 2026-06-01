from __future__ import annotations

import pytest

from backend.services.openai_model_service import OpenAIModelService


class FakeStore:
    def __init__(self, api_key: str = "sk-test"):
        self.api_key = api_key
        self.calls = []

    def api_key_for_scope(self, **kwargs):
        self.calls.append(kwargs)
        return self.api_key


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_list_models_for_scope_uses_stored_key_and_sorts_models(monkeypatch):
    store = FakeStore()
    captured = {}

    def fake_get(url, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "data": [
                    {"id": "gpt-z", "owned_by": "openai", "created": 3},
                    {"id": "gpt-a", "owned_by": "system", "created": 1},
                ]
            }
        )

    monkeypatch.setattr("backend.services.openai_model_service.requests.get", fake_get)

    service = OpenAIModelService(store, timeout_seconds=12)
    models = service.list_models_for_scope(scope="entity", entity_id=44)

    assert captured["url"] == "https://api.openai.com/v1/models"
    assert captured["headers"] == {"Authorization": "Bearer sk-test"}
    assert captured["timeout"] == 12
    assert store.calls == [{"scope": "entity", "provider": "openai", "entity_id": 44, "user_id": None}]
    assert models == [
        {"id": "gpt-a", "ownedBy": "system", "created": 1},
        {"id": "gpt-z", "ownedBy": "openai", "created": 3},
    ]


def test_list_models_for_scope_requires_saved_key():
    service = OpenAIModelService(FakeStore(api_key=""))

    with pytest.raises(ValueError, match="Save an OpenAI API key"):
        service.list_models_for_scope(scope="user", user_id=9)
