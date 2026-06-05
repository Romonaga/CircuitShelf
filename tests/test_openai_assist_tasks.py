from backend.services.openai_assist_tasks import finalizer_decision_reason


def test_finalizer_decision_reason_includes_useful_scope_details():
    reason = finalizer_decision_reason(
        question="What is a 555 timer chip?",
        answer="A 555 timer is a timing IC.",
        source_payload=[
            {
                "source": "ne555.pdf",
                "chunkCount": 3,
                "pages": [1, 2],
                "chunks": [{"preview": "timer"}],
            }
        ],
        provider_mode="always",
        effective_mode="always",
        confidence=0.89,
        min_confidence=0.8,
        build_card=None,
        issues=[],
    )

    assert "OpenAI answer validation ran because validation mode is always" in reason
    assert "What is a 555 timer chip?" in reason
    assert "1 source groups" in reason
    assert "3 retrieved chunks" in reason
    assert "2 cited pages" in reason
    assert "confidence 0.89" in reason


def test_finalizer_decision_reason_keeps_deterministic_issues():
    reason = finalizer_decision_reason(
        question="Wire this on a breadboard",
        answer="Connect pin 3 to the LED.",
        source_payload=[],
        provider_mode="auto",
        effective_mode="issues",
        confidence=0.95,
        min_confidence=0.8,
        build_card=None,
        issues=["The wiring answer does not mention ground/common-ground checks."],
    )

    assert "deterministic issues:" in reason
    assert "ground/common-ground checks" in reason
    assert "reviewed answer for 'Wire this on a breadboard'" in reason
