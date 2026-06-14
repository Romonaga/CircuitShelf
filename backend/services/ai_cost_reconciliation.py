from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import requests

from backend.services.ai_billing_reconciliation import (
    MONEY_QUANT,
    BillingUsageEvent,
    EventCostUpdate,
    reconcile_costs,
    verified_cost_from_openai_payload,
)


@dataclass(frozen=True)
class UsageCostEvent:
    event_id: int
    created_at: datetime
    provider: str
    model_name: str
    estimated_cost_usd: Decimal
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    provider_project_id: str = ""
    provider_api_key_id: str = ""


def reconcile_cost_bucket(
    events: list[UsageCostEvent],
    *,
    verified_cost_usd: Decimal,
    tolerance_usd: Decimal = Decimal("0.000001"),
    reconciliation_run_id: str | None = None,
    allocation_method: str = "estimated_cost_proportional",
) -> list[EventCostUpdate]:
    billing_events = [
        BillingUsageEvent(
            event_id=event.event_id,
            created_at=event.created_at,
            provider=event.provider,
            model_name=event.model_name,
            estimated_cost_usd=event.estimated_cost_usd,
            input_tokens=event.input_tokens,
            cached_input_tokens=event.cached_input_tokens,
            output_tokens=event.output_tokens,
            provider_project_id=event.provider_project_id,
            provider_api_key_id=event.provider_api_key_id,
        )
        for event in events
    ]
    return reconcile_costs(
        billing_events,
        verified_cost_usd=Decimal(str(verified_cost_usd)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP),
        tolerance_usd=tolerance_usd,
        reconciliation_run_id=reconciliation_run_id,
        allocation_method=allocation_method,
    ).updates


def reconciliation_diagnostics(
    events: list[UsageCostEvent],
    *,
    verified_cost_usd: Decimal,
) -> dict[str, Any]:
    result = reconcile_costs(
        [
            BillingUsageEvent(
                event_id=event.event_id,
                created_at=event.created_at,
                provider=event.provider,
                model_name=event.model_name,
                estimated_cost_usd=event.estimated_cost_usd,
                input_tokens=event.input_tokens,
                cached_input_tokens=event.cached_input_tokens,
                output_tokens=event.output_tokens,
                provider_project_id=event.provider_project_id,
                provider_api_key_id=event.provider_api_key_id,
            )
            for event in events
        ],
        verified_cost_usd=verified_cost_usd,
    )
    return result.diagnostics.as_dict()


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

