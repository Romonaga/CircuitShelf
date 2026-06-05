from datetime import datetime, timezone

from db.performance_store import PerformanceStore


def test_ai_work_row_uses_recorded_latency_as_duration():
    row = {
        "id": 7,
        "created_at": datetime(2026, 6, 5, 15, 0, tzinfo=timezone.utc),
        "entity_id": 1,
        "entity_name": "Blaise Works",
        "user_id": 1,
        "username": "hellweek",
        "task_label": "Answer validation",
        "task_type": "answer_validation",
        "model_name": "gpt-5-chat-latest",
        "context_type": "conversation",
        "context_id": "abc",
        "round_number": 1,
        "round_count": 1,
        "input_tokens": 100,
        "cached_input_tokens": 20,
        "output_tokens": 30,
        "estimated_cost": 0.0123,
        "paid_by": "user",
        "success": True,
        "error_message": None,
        "latency_ms": 5830,
    }

    mapped = PerformanceStore._ai_work_row(row)

    assert mapped["durationMs"] == 5830
    assert mapped["tokens"] == 150
