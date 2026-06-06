from __future__ import annotations

from backend.services.ingestion_ai_review_service import IngestionAiReviewService


class ReviewStore:
    def __init__(self):
        self.reviews = []

    def record_document_ingest_ai_review(self, **kwargs):
        self.reviews.append(kwargs)
        return 1


class OpenAiAssist:
    def __init__(self):
        self.calls = []

    def review_ingestion(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "provider": "openai",
            "model": "gpt-5-chat-latest",
            "paidBy": "system",
            "estimatedCost": 0.01,
            "review": {"quality": "usable"},
        }


class Logger:
    def __init__(self):
        self.messages = []

    def debug(self, message):
        self.messages.append(("debug", message))

    def info(self, message):
        self.messages.append(("info", message))

    def warning(self, message):
        self.messages.append(("warning", message))


def make_service(*, local_response, config=None):
    store = ReviewStore()
    openai = OpenAiAssist()

    def local_llm(_prompt, _model, **_kwargs):
        return local_response

    return (
        IngestionAiReviewService(
            config={"INGEST_LOCAL_AI_REVIEW_ENABLED": True, **(config or {})},
            trace_logger=Logger(),
            ai_provider_store=store,
            openai_assist_service=openai,
            query_local_llm=local_llm,
            local_model_name="electronics-helper:latest",
        ),
        store,
        openai,
    )


def component_stats():
    return {
        "rawChunkCount": 10,
        "chunkCount": 9,
        "extractedImageCount": 3,
        "indexedImageTextCount": 2,
        "ocrImageTextCount": 2,
    }


def test_component_datasheet_runs_local_review_without_openai_when_usable():
    service, store, openai = make_service(
        local_response=(
            '{"quality":"good","useful":true,"confidence":0.91,'
            '"warnings":[],"suggestedReviewFocus":"pinout","escalateToOpenAI":false,'
            '"reason":"deterministic extraction looks complete"}'
        )
    )

    result = service.review(
        source_path="MCP23017 datasheet.pdf",
        is_global=True,
        entity_id=None,
        user_id=1,
        stats=component_stats(),
        sample_text="MCP23017 data sheet pin configuration pin description electrical characteristics",
        openai_enabled=True,
    )

    assert result["provider"] == "ollama"
    assert result["paidBy"] == "local"
    assert result["estimatedCost"] == 0.0
    assert len(store.reviews) == 1
    assert store.reviews[0]["provider"] == "ollama"
    assert openai.calls == []


def test_local_review_can_escalate_to_openai_with_reason():
    service, store, openai = make_service(
        local_response=(
            '{"quality":"weak","useful":false,"confidence":0.42,'
            '"warnings":["pinout missing"],"suggestedReviewFocus":"pinout",'
            '"escalateToOpenAI":true,"reason":"pinout evidence is missing"}'
        )
    )

    result = service.review(
        source_path="4n35.pdf",
        is_global=True,
        entity_id=None,
        user_id=1,
        stats=component_stats(),
        sample_text="4N35 optocoupler data sheet electrical characteristics package DIP",
        openai_enabled=True,
    )

    assert result["provider"] == "ollama+openai"
    assert result["paidBy"] == "local->system"
    assert result["estimatedCost"] == 0.01
    assert len(store.reviews) == 1
    assert len(openai.calls) == 1
    assert "pinout evidence is missing" in openai.calls[0]["decision_reason"]


def test_general_book_skips_ai_review():
    service, store, openai = make_service(local_response='{"quality":"good"}')

    result = service.review(
        source_path="Electronics Projects For Dummies.pdf",
        is_global=True,
        entity_id=None,
        user_id=1,
        stats={
            "rawChunkCount": 900,
            "chunkCount": 880,
            "extractedImageCount": 20,
            "indexedImageTextCount": 20,
            "ocrImageTextCount": 20,
        },
        sample_text="This chapter introduces a breadboard project and explains how capacitors work.",
        openai_enabled=True,
    )

    assert result is None
    assert store.reviews == []
    assert openai.calls == []
