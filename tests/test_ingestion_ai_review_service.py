from __future__ import annotations

from backend.services.ingestion_ai_review_service import IngestionAiReviewService


class ReviewStore:
    def __init__(self):
        self.reviews = []
        self.events = []

    def record_document_ingest_ai_review(self, **kwargs):
        self.reviews.append(kwargs)
        return 1

    def record_ai_assist_event(self, **kwargs):
        self.events.append(kwargs)
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


def make_service(*, local_response, config=None, captured_local_kwargs=None):
    store = ReviewStore()
    openai = OpenAiAssist()

    def local_llm(_prompt, _model, **_kwargs):
        if captured_local_kwargs is not None:
            captured_local_kwargs.update(_kwargs)
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
    assert result["paidBy"] == "system"
    assert result["estimatedCost"] == 0.0
    assert len(store.reviews) == 1
    assert store.reviews[0]["provider"] == "ollama"
    assert store.reviews[0]["paid_by"] == "system"
    assert store.events[0]["paid_by"] == "system"
    assert openai.calls == []


def test_local_ingestion_review_uses_gpu_admission_backpressure():
    captured = {}
    service, store, openai = make_service(
        local_response=(
            '{"quality":"good","useful":true,"confidence":0.91,'
            '"warnings":[],"suggestedReviewFocus":"pinout","escalateToOpenAI":false,'
            '"reason":"deterministic extraction looks complete"}'
        ),
        config={
            "INGEST_LOCAL_AI_MAX_PENDING": 2,
            "INGEST_LOCAL_AI_ADMISSION_TIMEOUT_SECONDS": 45,
        },
        captured_local_kwargs=captured,
    )

    result = service.review(
        source_path="MCP23017 datasheet.pdf",
        is_global=True,
        entity_id=None,
        user_id=1,
        stats=component_stats(),
        sample_text="MCP23017 data sheet pin configuration pin description electrical characteristics",
        openai_enabled=False,
    )

    assert result["provider"] == "ollama"
    assert captured["gpu_resource_class"] == "local_llm"
    assert captured["gpu_owner"] == "ingest-ai"
    assert captured["gpu_admission_max_pending"] == 2
    assert captured["gpu_admission_timeout_seconds"] == 45.0


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
    assert result["paidBy"] == "system"
    assert result["estimatedCost"] == 0.01
    assert len(store.reviews) == 1
    assert len(openai.calls) == 1
    assert "pinout evidence is missing" in openai.calls[0]["decision_reason"]


def test_entity_private_local_review_records_entity_payer():
    service, store, openai = make_service(
        local_response=(
            '{"quality":"good","useful":true,"confidence":0.91,'
            '"warnings":[],"suggestedReviewFocus":"pinout","escalateToOpenAI":false,'
            '"reason":"deterministic extraction looks complete"}'
        )
    )

    result = service.review(
        source_path="private/MCP23017 datasheet.pdf",
        is_global=False,
        entity_id=7,
        user_id=1,
        stats=component_stats(),
        sample_text="MCP23017 data sheet pin configuration pin description electrical characteristics",
        openai_enabled=False,
    )

    assert result["provider"] == "ollama"
    assert result["paidBy"] == "entity"
    assert store.reviews[0]["paid_by"] == "entity"
    assert store.events[0]["entity_id"] == 7
    assert store.events[0]["paid_by"] == "entity"
    assert openai.calls == []


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


def test_component_datasheet_without_pinout_triggers_ai_review_from_intelligence():
    service, store, openai = make_service(
        local_response=(
            '{"quality":"weak","useful":false,"confidence":0.55,'
            '"warnings":["component datasheet lacks pinout"],"suggestedReviewFocus":"pinout table",'
            '"escalateToOpenAI":true,"reason":"pinout is missing"}'
        )
    )

    result = service.review(
        source_path="Espressif ESP32 datasheet.pdf",
        is_global=True,
        entity_id=None,
        user_id=1,
        stats={
            "rawChunkCount": 220,
            "chunkCount": 213,
            "extractedImageCount": 16,
            "indexedImageTextCount": 16,
            "ocrImageTextCount": 16,
        },
        sample_text="ESP32 Series Datasheet electrical characteristics recommended operating conditions",
        intelligence={
            "documentType": "component_datasheet",
            "componentName": "ESP32",
            "componentType": "microcontroller",
            "confidence": 0.91,
            "facts": [{"type": "voltage", "label": "VDD", "value": "3.3", "unit": "V"}],
            "pinout": {"pins": []},
        },
        openai_enabled=True,
    )

    assert result["provider"] == "ollama+openai"
    assert len(store.reviews) == 1
    assert len(openai.calls) == 1
    assert "has no detected pinout" in openai.calls[0]["decision_reason"]
