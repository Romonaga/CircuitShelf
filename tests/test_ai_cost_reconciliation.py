from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from backend.services.ai_cost_reconciliation import (
    OpenAIOrganizationUsageClient,
    UsageCostEvent,
    reconcile_cost_bucket,
    verified_cost_from_openai_payload,
)
from db.ai_provider_store import AIProviderStore


def test_reconcile_cost_bucket_allocates_verified_cost_proportionally():
    now = datetime.now(timezone.utc)
    events = [
        UsageCostEvent(
            event_id=1,
            created_at=now,
            provider="openai",
            model_name="gpt",
            estimated_cost_usd=Decimal("0.30"),
        ),
        UsageCostEvent(
            event_id=2,
            created_at=now,
            provider="openai",
            model_name="gpt",
            estimated_cost_usd=Decimal("0.70"),
        ),
    ]

    updates = reconcile_cost_bucket(events, verified_cost_usd=Decimal("1.20"), reconciliation_run_id="run-1")

    assert [update.event_id for update in updates] == [1, 2]
    assert updates[0].final_cost_usd == Decimal("0.36000000")
    assert updates[1].final_cost_usd == Decimal("0.84000000")
    assert updates[0].cost_status == "adjusted"
    assert updates[0].reconciliation_run_id == "run-1"


def test_reconcile_cost_bucket_ignores_local_events():
    now = datetime.now(timezone.utc)
    events = [
        UsageCostEvent(
            event_id=1,
            created_at=now,
            provider="ollama",
            model_name="local",
            estimated_cost_usd=Decimal("0"),
        )
    ]

    assert reconcile_cost_bucket(events, verified_cost_usd=Decimal("1.20")) == []


def test_verified_cost_from_openai_payload_sums_cost_results():
    payload = {
        "data": [
            {"results": [{"amount": {"value": 0.06, "currency": "usd"}}, {"amount": {"value": "0.02"}}]},
            {"results": [{"amount": {"value": 0.10}}]},
        ]
    }

    assert verified_cost_from_openai_payload(payload) == Decimal("0.18000000")


def test_openai_organization_usage_client_paginates_costs(monkeypatch):
    calls: list[dict] = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, *, headers, params, timeout):
        calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        if "page" not in params:
            return Response({"data": [{"start_time": 1, "results": []}], "has_more": True, "next_page": "next"})
        return Response({"data": [{"start_time": 2, "results": []}], "has_more": False, "next_page": None})

    monkeypatch.setattr("backend.services.ai_cost_reconciliation.requests.get", fake_get)
    client = OpenAIOrganizationUsageClient(admin_api_key="admin-key", base_url="https://api.openai.test/v1")

    payload = client.fetch_costs(start_time=100, end_time=200, group_by=["api_key_id"], api_key_ids=["key-1"])

    assert payload["data"] == [{"start_time": 1, "results": []}, {"start_time": 2, "results": []}]
    assert calls[0]["url"] == "https://api.openai.test/v1/organization/costs"
    assert calls[0]["headers"]["Authorization"] == "Bearer admin-key"
    assert calls[0]["params"]["api_key_ids"] == ["key-1"]
    assert calls[1]["params"]["page"] == "next"


def test_openai_organization_usage_client_requires_admin_key():
    with pytest.raises(ValueError, match="admin API key"):
        OpenAIOrganizationUsageClient(admin_api_key="")


def test_usage_event_row_exposes_reconciliation_fields():
    row = {
        "id": 12,
        "created_at": None,
        "entity_id": None,
        "entity_name": None,
        "user_id": None,
        "username": "hellweek",
        "provider": "openai",
        "task_type": "photo_check",
        "task_label": "Photo check",
        "model_name": "gpt",
        "context_type": "bench",
        "context_id": None,
        "round_number": 1,
        "round_count": 1,
        "input_tokens": 100,
        "cached_input_tokens": 10,
        "output_tokens": 20,
        "estimated_cost": Decimal("0.01000000"),
        "final_cost": Decimal("0.01250000"),
        "cost_status": "adjusted",
        "cost_discrepancy": Decimal("0.00250000"),
        "reconciliation_run_id": "11111111-1111-1111-1111-111111111111",
        "allocation_method": "estimated_cost_proportional",
        "paid_by": "system",
        "provider_key_owner_user_id": None,
        "provider_key_owner_username": None,
        "success": True,
        "error_message": None,
        "decision_reason": "test",
        "latency_ms": 1000,
    }

    event = AIProviderStore(database=None, config_path="config/config.yaml")._usage_event_row(row)

    assert event["estimatedCost"] == 0.01
    assert event["finalCost"] == 0.0125
    assert event["billableCost"] == 0.0125
    assert event["costStatus"] == "adjusted"
    assert event["costDiscrepancy"] == 0.0025
    assert event["reconciliationRunId"] == "11111111-1111-1111-1111-111111111111"


def test_usage_summary_row_exposes_estimated_actual_and_verified_costs():
    row = {
        "calls": 614,
        "successful_calls": 612,
        "input_tokens": 1000,
        "cached_input_tokens": 25,
        "output_tokens": 250,
        "estimated_cost": Decimal("2.14801400"),
        "actual_cost": Decimal("6.96919945"),
        "verified_cost": Decimal("6.96919945"),
        "reconciled_calls": 191,
    }

    summary = AIProviderStore(database=None, config_path="config/config.yaml")._usage_summary_row(row)

    assert summary["calls"] == 614
    assert summary["successfulCalls"] == 612
    assert summary["tokens"] == 1275
    assert summary["estimatedCost"] == 2.148014
    assert summary["actualCost"] == 6.96919945
    assert summary["billableCost"] == 6.96919945
    assert summary["verifiedCost"] == 6.96919945
    assert summary["finalCost"] == 6.96919945
    assert summary["reconciledCalls"] == 191


def test_usage_cost_timeline_row_maps_daily_cost_comparison():
    row = {
        "bucket_date": date(2026, 6, 13),
        "calls": 25,
        "reconciled_calls": 12,
        "estimated_cost": Decimal("0.50"),
        "actual_cost": Decimal("1.25"),
        "verified_cost": Decimal("1.10"),
    }

    point = AIProviderStore(database=None, config_path="config/config.yaml")._usage_cost_timeline_row(row)

    assert point == {
        "date": "2026-06-13",
        "calls": 25,
        "reconciledCalls": 12,
        "estimatedCost": 0.5,
        "actualCost": 1.25,
        "verifiedCost": 1.1,
    }
