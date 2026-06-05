from __future__ import annotations

import csv
from io import StringIO
from typing import Any


AI_USAGE_CSV_FIELDS = [
    "createdAt",
    "entityName",
    "username",
    "provider",
    "taskType",
    "taskLabel",
    "modelName",
    "contextType",
    "contextId",
    "roundNumber",
    "roundCount",
    "inputTokens",
    "cachedInputTokens",
    "outputTokens",
    "estimatedCost",
    "paidBy",
    "providerKeyOwnerUsername",
    "decisionReason",
    "latencyMs",
    "success",
    "errorMessage",
]


def ai_usage_report_to_csv(report: dict[str, Any]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=AI_USAGE_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for event in report.get("events") or []:
        writer.writerow({field: event.get(field, "") for field in AI_USAGE_CSV_FIELDS})
    return output.getvalue()
