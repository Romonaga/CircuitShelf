from __future__ import annotations

"""Reusable AI billing estimation and reconciliation primitives.

This module intentionally has no database dependency. Applications pass in the
usage they captured locally, optional provider billing filters, pricing rows,
and provider actual-cost payloads. The module returns estimated costs,
proportional reconciliation updates, and diagnostics that explain whether the
estimate and provider actuals line up.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import uuid4

MONEY_QUANT = Decimal("0.00000001")
RATE_QUANT = Decimal("0.000001")


@dataclass(frozen=True)
class BillingCapture:
    provider: str
    model_name: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    provider_project_id: str = ""
    provider_api_key_id: str = ""
    provider_request_id: str = ""
    service_tier: str = ""

    def as_event_fields(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "input_tokens": max(0, int(self.input_tokens or 0)),
            "cached_input_tokens": max(0, int(self.cached_input_tokens or 0)),
            "output_tokens": max(0, int(self.output_tokens or 0)),
            "provider_project_id": self.provider_project_id,
            "provider_api_key_id": self.provider_api_key_id,
            "provider_request_id": self.provider_request_id,
            "service_tier": self.service_tier,
        }


@dataclass(frozen=True)
class BillingPricing:
    model_name: str
    input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal
    currency: str = "USD"


@dataclass(frozen=True)
class BillingUsageEvent:
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
    service_tier: str = ""


@dataclass(frozen=True)
class BillingReconciliationFilters:
    project_ids: list[str] = field(default_factory=list)
    api_key_ids: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)

    def normalized(self) -> "BillingReconciliationFilters":
        project_ids = _unique_clean(self.project_ids)
        api_key_ids = _unique_clean(self.api_key_ids)
        group_by = _unique_clean(self.group_by)
        if api_key_ids and "api_key_id" not in group_by:
            group_by.append("api_key_id")
        return BillingReconciliationFilters(project_ids=project_ids, api_key_ids=api_key_ids, group_by=group_by)

    def as_provider_params(self) -> dict[str, list[str]]:
        normalized = self.normalized()
        return {
            "project_ids": normalized.project_ids,
            "api_key_ids": normalized.api_key_ids,
            "group_by": normalized.group_by,
        }


@dataclass(frozen=True)
class EventCostUpdate:
    event_id: int
    estimated_cost_usd: Decimal
    final_cost_usd: Decimal
    cost_status: str
    cost_discrepancy_usd: Decimal
    reconciliation_run_id: str
    allocation_method: str


@dataclass(frozen=True)
class EstimateDiagnostics:
    estimated_cost_usd: Decimal
    verified_cost_usd: Decimal
    discrepancy_usd: Decimal
    actual_to_estimate_ratio: Decimal | None
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    effective_total_per_million: Decimal | None
    inferred_output_per_million: Decimal | None
    warnings: list[str]
    notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "estimatedCost": _decimal_or_none(self.estimated_cost_usd),
            "verifiedCost": _decimal_or_none(self.verified_cost_usd),
            "discrepancy": _decimal_or_none(self.discrepancy_usd),
            "actualToEstimateRatio": _decimal_or_none(self.actual_to_estimate_ratio),
            "inputTokens": self.input_tokens,
            "cachedInputTokens": self.cached_input_tokens,
            "outputTokens": self.output_tokens,
            "effectiveTotalPerMillion": _decimal_or_none(self.effective_total_per_million),
            "inferredOutputPerMillion": _decimal_or_none(self.inferred_output_per_million),
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ReconciliationResult:
    updates: list[EventCostUpdate]
    diagnostics: EstimateDiagnostics
    allocation_method: str
    reconciliation_run_id: str


def capture_from_openai_response(
    *,
    model_name: str,
    usage: dict[str, Any],
    provider_project_id: str = "",
    provider_api_key_id: str = "",
    provider_request_id: str = "",
    service_tier: str = "",
) -> BillingCapture:
    return BillingCapture(
        provider="openai",
        model_name=model_name,
        input_tokens=int(usage.get("inputTokens") or usage.get("input_tokens") or 0),
        cached_input_tokens=int(usage.get("cachedInputTokens") or usage.get("cached_input_tokens") or 0),
        output_tokens=int(usage.get("outputTokens") or usage.get("output_tokens") or 0),
        provider_project_id=str(provider_project_id or ""),
        provider_api_key_id=str(provider_api_key_id or ""),
        provider_request_id=str(provider_request_id or ""),
        service_tier=str(service_tier or ""),
    )


def capture_from_openai_response_payload(
    payload: dict[str, Any],
    *,
    model_name: str = "",
    provider_project_id: str = "",
    provider_api_key_id: str = "",
) -> BillingCapture:
    usage = payload.get("usage") or {}
    input_details = usage.get("input_tokens_details") or {}
    return BillingCapture(
        provider="openai",
        model_name=str(model_name or payload.get("model") or ""),
        input_tokens=int(usage.get("input_tokens") or 0),
        cached_input_tokens=int(input_details.get("cached_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        provider_project_id=str(provider_project_id or ""),
        provider_api_key_id=str(provider_api_key_id or ""),
        provider_request_id=str(payload.get("id") or ""),
        service_tier=str(payload.get("service_tier") or ""),
    )


def estimate_event_cost(capture: BillingCapture, pricing: BillingPricing) -> Decimal:
    regular_input_tokens = max(0, int(capture.input_tokens or 0) - int(capture.cached_input_tokens or 0))
    cached_input_tokens = max(0, int(capture.cached_input_tokens or 0))
    output_tokens = max(0, int(capture.output_tokens or 0))
    cost = (
        Decimal(regular_input_tokens) * pricing.input_per_million
        + Decimal(cached_input_tokens) * pricing.cached_input_per_million
        + Decimal(output_tokens) * pricing.output_per_million
    ) / Decimal(1_000_000)
    return cost.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def reconcile_costs(
    events: list[BillingUsageEvent],
    *,
    verified_cost_usd: Decimal,
    pricing_by_model: dict[str, BillingPricing] | None = None,
    billable_provider: str = "openai",
    tolerance_usd: Decimal = Decimal("0.000001"),
    reconciliation_run_id: str | None = None,
    allocation_method: str = "estimated_cost_proportional",
) -> ReconciliationResult:
    billable_events = [event for event in events if event.provider == billable_provider]
    run_id = reconciliation_run_id or str(uuid4())
    verified = Decimal(str(verified_cost_usd)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    diagnostics = diagnose_estimate_accuracy(
        billable_events,
        verified_cost_usd=verified,
        pricing_by_model=pricing_by_model or {},
    )
    if not billable_events:
        return ReconciliationResult(updates=[], diagnostics=diagnostics, allocation_method=allocation_method, reconciliation_run_id=run_id)

    bucket_status = "verified" if abs(diagnostics.discrepancy_usd) <= tolerance_usd else "adjusted"
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
    return ReconciliationResult(updates=updates, diagnostics=diagnostics, allocation_method=allocation_method, reconciliation_run_id=run_id)


def diagnose_estimate_accuracy(
    events: list[BillingUsageEvent],
    *,
    verified_cost_usd: Decimal,
    pricing_by_model: dict[str, BillingPricing] | None = None,
) -> EstimateDiagnostics:
    verified = Decimal(str(verified_cost_usd)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    estimated = sum((event.estimated_cost_usd for event in events), Decimal("0")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    input_tokens = sum(max(0, int(event.input_tokens or 0)) for event in events)
    cached_input_tokens = sum(max(0, int(event.cached_input_tokens or 0)) for event in events)
    output_tokens = sum(max(0, int(event.output_tokens or 0)) for event in events)
    total_tokens = input_tokens + output_tokens
    ratio = None if estimated <= 0 else (verified / estimated).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    effective_total = None
    if total_tokens > 0:
        effective_total = (verified * Decimal(1_000_000) / Decimal(total_tokens)).quantize(RATE_QUANT, rounding=ROUND_HALF_UP)
    inferred_output = _infer_output_rate(events, verified_cost_usd=verified, pricing_by_model=pricing_by_model or {})
    warnings: list[str] = []
    notes: list[str] = []

    if not events and verified > 0:
        warnings.append("Provider reported verified cost but no local usage events matched the reconciliation scope.")
    if events and verified <= 0:
        warnings.append("Local usage events matched the reconciliation scope but provider verified cost is zero.")
    if any(not event.provider_project_id for event in events):
        warnings.append("Some local events are missing provider project IDs; project-scoped reconciliation may mix costs.")
    if any(not event.provider_api_key_id for event in events):
        warnings.append("Some local events are missing provider API key IDs; key-scoped reconciliation may mix costs.")
    if ratio is not None and ratio < Decimal("0.80"):
        warnings.append("Verified cost is materially lower than local estimates; check key/window mapping, service tier, cached-token handling, and model pricing.")
    if ratio is not None and ratio > Decimal("1.20"):
        warnings.append("Verified cost is materially higher than local estimates; check missing events, untracked keys, model pricing, and provider surcharges.")
    if inferred_output is not None and pricing_by_model:
        notes.append("Inferred output rate holds configured input and cached-input rates constant; large drift usually means pricing, tier, or scope mismatch.")

    return EstimateDiagnostics(
        estimated_cost_usd=estimated,
        verified_cost_usd=verified,
        discrepancy_usd=(verified - estimated).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP),
        actual_to_estimate_ratio=ratio,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        effective_total_per_million=effective_total,
        inferred_output_per_million=inferred_output,
        warnings=warnings,
        notes=notes,
    )


def verified_cost_from_openai_payload(payload: dict[str, Any]) -> Decimal:
    total = Decimal("0")
    for bucket in payload.get("data") or []:
        for result in bucket.get("results") or []:
            amount = result.get("amount") or {}
            total += Decimal(str(amount.get("value") or "0"))
    return total.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _infer_output_rate(
    events: list[BillingUsageEvent],
    *,
    verified_cost_usd: Decimal,
    pricing_by_model: dict[str, BillingPricing],
) -> Decimal | None:
    if not events or not pricing_by_model:
        return None
    known_input_cost = Decimal("0")
    output_tokens = 0
    for event in events:
        pricing = pricing_by_model.get(event.model_name)
        if not pricing:
            return None
        regular_input_tokens = max(0, int(event.input_tokens or 0) - int(event.cached_input_tokens or 0))
        cached_input_tokens = max(0, int(event.cached_input_tokens or 0))
        known_input_cost += (
            Decimal(regular_input_tokens) * pricing.input_per_million
            + Decimal(cached_input_tokens) * pricing.cached_input_per_million
        ) / Decimal(1_000_000)
        output_tokens += max(0, int(event.output_tokens or 0))
    if output_tokens <= 0:
        return None
    remaining_output_cost = Decimal(str(verified_cost_usd)) - known_input_cost
    return (remaining_output_cost * Decimal(1_000_000) / Decimal(output_tokens)).quantize(RATE_QUANT, rounding=ROUND_HALF_UP)


def _allocate_verified_costs(events: list[BillingUsageEvent], verified_cost_usd: Decimal) -> list[Decimal]:
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


def _unique_clean(values: list[str] | None) -> list[str]:
    clean: list[str] = []
    for value in values or []:
        item = str(value or "").strip()
        if item and item not in clean:
            clean.append(item)
    return clean


def _decimal_or_none(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)
