from __future__ import annotations

from backend.services.project_finder_ai_triage import ProjectFinderAiTriageService, normalize_project_finder_reviews


class Store:
    def __init__(self):
        self.events = []

    def record_ai_assist_event(self, **kwargs):
        self.events.append(kwargs)
        return 1


class OpenAi:
    def __init__(self, result=None):
        self.calls = []
        self.result = result

    def triage_project_finder(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class Logger:
    def warning(self, _message):
        pass


def candidate(candidate_id="candidate-1", *, score=40):
    return {
        "id": candidate_id,
        "title": "555 timer starter",
        "score": score,
        "buildable": False,
        "projectLike": True,
        "summary": "Build a 555 timer LED flasher.",
        "matchedParts": [{"displayName": "LM555"}],
        "requiredParts": [{"name": "NE555 timer"}],
        "missingParts": [{"name": "Breadboard"}],
        "matchReasons": [],
        "rejectionReasons": [],
    }


def response_with(candidate_payload):
    return {
        "candidateCount": 1,
        "candidates": [candidate_payload],
    }


def make_service(*, local_response, openai_result=None, config=None):
    store = Store()
    openai = OpenAi(openai_result)

    def local_llm(_prompt, _model, **_kwargs):
        return local_response

    return (
        ProjectFinderAiTriageService(
            config={"PROJECT_FINDER_AI_TRIAGE_ENABLED": True, **(config or {})},
            trace_logger=Logger(),
            ai_provider_store=store,
            openai_assist_service=openai,
            query_local_llm=local_llm,
            local_model_name="electronics-helper:latest",
        ),
        store,
        openai,
    )


def test_local_project_finder_triage_records_usage_without_openai():
    service, store, openai = make_service(
        local_response=(
            '{"candidates":[{"id":"candidate-1","useful":true,"confidence":0.86,'
            '"recommendedAction":"keep","notes":["good project evidence"],'
            '"escalateToOpenAI":false,"reason":"candidate is grounded"}]}'
        )
    )
    payload = response_with(candidate())

    result = service.triage_response(payload, entity_id=5, user_id=7)

    assert result["aiTriage"]["localReviewedCount"] == 1
    assert result["aiTriage"]["openaiReviewedCount"] == 0
    assert openai.calls == []
    assert store.events[0]["provider"] == "ollama"
    assert store.events[0]["task_type"] == "project_finder"
    assert store.events[0]["paid_by"] == "entity"
    assert result["candidates"][0]["aiTriage"]["provider"] == "ollama"
    assert "AI triage" in result["candidates"][0]["matchReasons"][0]


def test_project_finder_triage_escalates_low_confidence_local_review_to_openai():
    service, store, openai = make_service(
        local_response=(
            '{"candidates":[{"id":"candidate-1","useful":true,"confidence":0.32,'
            '"recommendedAction":"manual_review","notes":["ambiguous"],'
            '"escalateToOpenAI":true,"reason":"local evidence is ambiguous"}]}'
        ),
        openai_result={
            "provider": "openai",
            "model": "gpt-5-chat-latest",
            "candidates": [
                {
                    "id": "candidate-1",
                    "useful": False,
                    "confidence": 0.72,
                    "recommendedAction": "demote",
                    "notes": ["not enough build detail"],
                    "escalateToOpenAI": False,
                    "reason": "source is not build-ready",
                }
            ],
        },
    )
    payload = response_with(candidate())

    result = service.triage_response(payload, entity_id=None, user_id=7)

    assert len(openai.calls) == 1
    assert openai.calls[0]["candidates"][0]["id"] == "candidate-1"
    assert result["aiTriage"]["escalated"] is True
    assert result["aiTriage"]["openaiReviewedCount"] == 1
    assert store.events[0]["paid_by"] == "user"
    assert result["candidates"][0]["aiTriage"]["provider"] == "ollama+openai"
    assert "source is not build-ready" in result["candidates"][0]["rejectionReasons"][0]


def test_project_finder_triage_ignores_high_score_candidates():
    service, store, openai = make_service(local_response='{"candidates":[]}')
    payload = response_with(candidate(score=140))

    result = service.triage_response(payload, entity_id=5, user_id=7)

    assert result["aiTriage"]["reviewedCount"] == 0
    assert store.events == []
    assert openai.calls == []


def test_normalize_project_finder_reviews_clamps_shape():
    reviews = normalize_project_finder_reviews(
        {
            "candidates": [
                {
                    "id": "a",
                    "useful": False,
                    "confidence": 5,
                    "recommendedAction": "unknown",
                    "notes": "check manually",
                }
            ]
        }
    )

    assert reviews == [
        {
            "id": "a",
            "useful": False,
            "confidence": 1.0,
            "recommendedAction": "manual_review",
            "notes": ["check manually"],
            "escalateToOpenAI": False,
            "reason": "",
        }
    ]
