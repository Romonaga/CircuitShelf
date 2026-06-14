from __future__ import annotations

from typing import Any


class OpenAIAssistAccountingMixin:
    ai_provider_store: Any

    def _assist_event_base(
        self,
        *,
        settings: dict[str, Any],
        entity_id: int | None,
        user_id: int | None,
        task_type: str,
        context_type: str = "",
        context_id: str | None = None,
        round_number: int = 1,
        round_count: int = 1,
        decision_reason: str = "",
    ) -> dict[str, Any]:
        return {
            "entity_id": entity_id,
            "user_id": user_id,
            "provider": "openai",
            "task_type": task_type,
            "model_name": settings["modelName"],
            "context_type": context_type,
            "context_id": context_id,
            "round_number": round_number,
            "round_count": round_count,
            "decision_reason": decision_reason,
            "paid_by": settings["paidBy"],
            "provider_key_owner_user_id": settings.get("providerKeyOwnerUserId"),
            "provider_project_id": settings.get("providerProjectId") or "",
            "provider_api_key_id": settings.get("providerApiKeyId") or "",
        }

    def _estimate_openai_cost(self, settings: dict[str, Any], usage: dict[str, int]) -> float:
        return self.ai_provider_store.estimate_cost(
            provider="openai",
            model_name=settings["modelName"],
            input_tokens=usage["inputTokens"],
            cached_input_tokens=usage["cachedInputTokens"],
            output_tokens=usage["outputTokens"],
            billing_scope=settings["pricingScope"],
            entity_id=settings.get("pricingEntityId"),
            user_id=settings.get("pricingUserId"),
        )

    def _record_ai_success(
        self,
        event_base: dict[str, Any],
        usage: dict[str, int],
        estimated_cost: float,
        *,
        latency_ms: int = 0,
    ) -> None:
        self.ai_provider_store.record_ai_assist_event(
            **event_base,
            input_tokens=usage["inputTokens"],
            cached_input_tokens=usage["cachedInputTokens"],
            output_tokens=usage["outputTokens"],
            estimated_cost=estimated_cost,
            latency_ms=latency_ms,
            success=True,
        )

    def _record_ai_failure(self, event_base: dict[str, Any], message: str, *, latency_ms: int = 0) -> None:
        self.ai_provider_store.record_ai_assist_event(
            **event_base,
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            estimated_cost=0,
            latency_ms=latency_ms,
            success=False,
            error_message=message,
        )

    def _record_budget_block_if_needed(self, event_base: dict[str, Any], settings: dict[str, Any]) -> str:
        message = self._budget_block_message(settings)
        if message:
            self._record_ai_failure(event_base, message)
        return message

    def _budget_block_message(self, settings: dict[str, Any]) -> str:
        status = self.ai_provider_store.budget_status_for_settings(settings)
        if not status.get("blocked"):
            return ""
        return (
            f"OpenAI assist budget exceeded for {settings.get('paidBy') or 'unknown'} payer: "
            f"${status.get('monthSpend', 0):.4f} spent this month, "
            f"stop threshold ${status.get('stopAt', 0):.4f}."
        )
