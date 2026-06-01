from __future__ import annotations

import csv
from io import StringIO

from backend.services.ai_usage_export import ai_usage_report_to_csv


def test_ai_usage_report_to_csv_exports_audited_rows():
    text = ai_usage_report_to_csv(
        {
            "events": [
                {
                    "createdAt": "2026-05-31T12:00:00Z",
                    "entityName": "Blaise Works",
                    "username": "hellweek",
                    "provider": "openai",
                    "taskType": "answer_validation",
                    "taskLabel": "Answer validation",
                    "modelName": "gpt-5-chat-latest",
                    "contextType": "conversation",
                    "contextId": "abc",
                    "roundNumber": 1,
                    "roundCount": 1,
                    "inputTokens": 10,
                    "cachedInputTokens": 2,
                    "outputTokens": 20,
                    "estimatedCost": 0.001,
                    "paidBy": "entity",
                    "providerKeyOwnerUsername": "",
                    "success": True,
                    "errorMessage": "",
                }
            ]
        }
    )

    rows = list(csv.DictReader(StringIO(text)))
    assert len(rows) == 1
    assert rows[0]["entityName"] == "Blaise Works"
    assert rows[0]["username"] == "hellweek"
    assert rows[0]["estimatedCost"] == "0.001"
