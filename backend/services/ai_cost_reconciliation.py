from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import uuid4

import requests

MONEY_QUANT = Decimal("0.00000001")


@dataclass(frozen=True)
class UsageCostEvent:
    event_id: int
    created_at: datetime
    provider: str
    model_name: str
    estimated_cost_usd: Decimal


@dataclass(frozen=True)
class EventCostUpdate:
    event_id: int
    estimated_cost_usd: Decimal
    final_cost_usd: Decimal
    cost_status: str
    cost_discrepancy_usd: Decimal
    reconciliation_run_id: str
    allocation_method: str


def reconcile_cost_bucket(
    events: list[UsageCostEvent],
    *,
    verified_cost_usd: Decimal,
    tolerance_usd: Decimal = Decimal("0.000001"),
    reconciliation_run_id: str | None = None,
    allocation_method: str = "estimated_cost_proportional",
) -> list[EventCostUpdate]:
    billable_events = [event for event in events if event.provider == "openai"]
    if not billable_events:
        return []

    run_id = reconciliation_run_id or str(uuid4())
    verified = Decimal(str(verified_cost_usd)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    estimated_total = sum((event.estimated_cost_usd for event in billable_events), Decimal("0")).quantize(
        MONEY_QUANT,
        rounding=ROUND_HALF_UP,
    )
    total_discrepancy = (verified - estimated_total).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    bucket_status = "verified" if abs(total_discrepancy) <= tolerance_usd else "adjusted"
    allocated = _allocate_verified_costs(billable_events, verified)

    updates: list[EventCostUpdate] = []
    for event, final_cost in zip(billable_events, allocated, strict=True):
        discrepancy = (final_cost - event.estimated_cost_usd).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        updates.append(
            EventCostUpdate(
                event_id=event.event_id,
                estimated_cost_usd=event.estimated_cost_usd,
                final_cost_usd=final_cost,
                cost_status=bucket_status,
                cost_discrepancy_usd=discrepancy,
                reconciliation_run_id=run_id,
                allocation_method=allocation_method,
            )
        )
    return updates


def verified_cost_from_openai_payload(payload: dict[str, Any]) -> Decimal:
    total = Decimal("0")
    for bucket in payload.get("data") or []:
        for result in bucket.get("results") or []:
            amount = result.get("amount") or {}
            total += Decimal(str(amount.get("value") or "0"))
    return total.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


class OpenAIOrganizationUsageClient:
    def __init__(
        self,
        *,
        admin_api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30,
    ):
        self.admin_api_key = str(admin_api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        if not self.admin_api_key:
            raise ValueError("OpenAI admin API key is required for organization cost reconciliation.")

    def fetch_costs(
        self,
        *,
        start_time: int,
        end_time: int | None = None,
        bucket_width: str = "1d",
        group_by: list[str] | None = None,
        project_ids: list[str] | None = None,
        api_key_ids: list[str] | None = None,
        limit: int = 180,
    ) -> dict[str, Any]:
        return self._get_paginated(
            "/organization/costs",
            {
                "start_time": start_time,
                "end_time": end_time,
                "bucket_width": bucket_width,
                "group_by": group_by,
                "project_ids": project_ids,
                "api_key_ids": api_key_ids,
                "limit": limit,
            },
        )

    def _get_paginated(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        clean_params = {key: value for key, value in params.items() if value not in (None, [], "")}
        headers = {"Authorization": f"Bearer {self.admin_api_key}", "Content-Type": "application/json"}
        buckets: list[dict[str, Any]] = []
        page: str | None = None

        while True:
            request_params = dict(clean_params)
            if page:
                request_params["page"] = page
            response = requests.get(
                f"{self.base_url}{path}",
                headers=headers,
                params=request_params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            buckets.extend(payload.get("data") or [])
            page = payload.get("next_page")
            if not payload.get("has_more") or not page:
                return {"object": "page", "data": buckets, "has_more": False, "next_page": None}


def _allocate_verified_costs(events: list[UsageCostEvent], verified_cost_usd: Decimal) -> list[Decimal]:
    if len(events) == 1:
        return [verified_cost_usd.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)]

    estimated_total = sum((event.estimated_cost_usd for event in events), Decimal("0"))
    if estimated_total <= 0:
        weights = [Decimal(1) / Decimal(len(events)) for _ in events]
    else:
        weights = [event.estimated_cost_usd / estimated_total for event in events]

    allocated: list[Decimal] = []
    remaining = verified_cost_usd
    for index, weight in enumerate(weights):
        if index == len(weights) - 1:
            final_cost = remaining
        else:
            final_cost = (verified_cost_usd * weight).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            remaining -= final_cost
        allocated.append(final_cost.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))
    return allocated
