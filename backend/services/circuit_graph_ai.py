from __future__ import annotations

import time
from typing import Any, Callable

from backend.services.ingestion_ai_review_service import estimate_local_tokens, optional_float
from backend.services.openai_assist_prompts import (
    LOCAL_CIRCUIT_GRAPH_ENRICHMENT_SYSTEM_PROMPT,
    build_circuit_graph_enrichment_prompt,
)
from backend.services.openai_assist_utils import parse_json_object


class CircuitGraphAiEnrichmentService:
    def __init__(
        self,
        *,
        ai_provider_store: Any,
        openai_assist_service: Any | None,
        query_local_llm: Callable[..., str] | None,
        local_model_name: str | None,
        trace_logger: Any = None,
    ):
        self.ai_provider_store = ai_provider_store
        self.openai_assist_service = openai_assist_service
        self.query_local_llm = query_local_llm
        self.local_model_name = local_model_name
        self.trace_logger = trace_logger

    def enrich(
        self,
        *,
        plan: dict[str, Any],
        graph: dict[str, Any],
        entity_id: int | None,
        user_id: int | None,
    ) -> dict[str, Any]:
        decision_reason = (
            f"Circuit graph enrichment requested for assembly plan {plan.get('id') or 'unknown'}; "
            f"deterministic status={graph.get('status')}."
        )
        local_review = self._run_local_review(plan=plan, graph=graph)
        if local_review:
            self._record_local_event(
                local_review,
                entity_id=entity_id,
                user_id=user_id,
                decision_reason=decision_reason,
            )

        openai_review = None
        if self._should_escalate_to_openai(local_review):
            openai_review = self._run_openai_review(
                plan=plan,
                graph=graph,
                local_review=local_review,
                entity_id=entity_id,
                user_id=user_id,
                decision_reason=f"{decision_reason} Local enrichment requested or required escalation.",
            )

        return {
            "enabled": True,
            "local": normalize_circuit_graph_enrichment(local_review) if local_review else None,
            "openai": normalize_circuit_graph_enrichment(openai_review) if openai_review else None,
            "provider": "ollama+openai" if openai_review else ("ollama" if local_review else "none"),
            "escalated": bool(openai_review),
        }

    def _run_local_review(self, *, plan: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any] | None:
        if not self.query_local_llm or not self.local_model_name:
            return None
        system_prompt = LOCAL_CIRCUIT_GRAPH_ENRICHMENT_SYSTEM_PROMPT
        prompt = build_circuit_graph_enrichment_prompt(plan=plan, graph=graph)
        started_at = time.time()
        try:
            raw = self.query_local_llm(
                prompt,
                self.local_model_name,
                chat_history=[],
                system_prompt=system_prompt,
                gpu_priority=85,
                gpu_owner="circuit-graph-ai",
                gpu_resource_class="local_llm",
                keep_alive=0,
            )
            parsed = parse_json_object(raw)
            parsed["raw"] = str(raw or "")[:4000]
            parsed["_inputTokenEstimate"] = estimate_local_tokens(system_prompt) + estimate_local_tokens(prompt)
            parsed["_outputTokenEstimate"] = estimate_local_tokens(raw)
            parsed["_latencyMs"] = int((time.time() - started_at) * 1000)
            parsed["_success"] = True
            parsed["provider"] = "ollama"
            parsed["model"] = self.local_model_name
            return parsed
        except Exception as exc:
            if self.trace_logger:
                self.trace_logger.warning(f"Local circuit graph enrichment failed: {exc}")
            return {
                "useful": False,
                "confidence": 0.0,
                "summary": "Local circuit graph enrichment failed.",
                "proposedPins": [],
                "proposedNets": [],
                "proposedConnections": [],
                "validationFindings": ["Local AI could not review the circuit graph."],
                "escalateToOpenAI": True,
                "reason": "local circuit graph enrichment failed",
                "raw": "",
                "_inputTokenEstimate": 0,
                "_outputTokenEstimate": 0,
                "_latencyMs": int((time.time() - started_at) * 1000),
                "_success": False,
                "_errorMessage": str(exc)[:240],
                "provider": "ollama",
                "model": self.local_model_name,
            }

    def _record_local_event(
        self,
        result: dict[str, Any],
        *,
        entity_id: int | None,
        user_id: int | None,
        decision_reason: str,
    ) -> None:
        if not self.ai_provider_store or not hasattr(self.ai_provider_store, "record_ai_assist_event"):
            return
        paid_by = "entity" if entity_id is not None else ("user" if user_id is not None else "unknown")
        self.ai_provider_store.record_ai_assist_event(
            entity_id=entity_id,
            user_id=user_id,
            provider="ollama",
            task_type="circuit_graph",
            model_name=self.local_model_name or "local",
            context_type="assembly_plan",
            input_tokens=int(result.get("_inputTokenEstimate") or 0),
            output_tokens=int(result.get("_outputTokenEstimate") or 0),
            estimated_cost=0.0,
            paid_by=paid_by,
            success=bool(result.get("_success", True)),
            error_message=result.get("_errorMessage"),
            decision_reason=decision_reason,
            latency_ms=int(result.get("_latencyMs") or 0),
        )

    def _run_openai_review(
        self,
        *,
        plan: dict[str, Any],
        graph: dict[str, Any],
        local_review: dict[str, Any] | None,
        entity_id: int | None,
        user_id: int | None,
        decision_reason: str,
    ) -> dict[str, Any] | None:
        if not self.openai_assist_service or not hasattr(self.openai_assist_service, "enrich_circuit_graph"):
            return None
        return self.openai_assist_service.enrich_circuit_graph(
            plan=plan,
            graph=graph,
            local_review=normalize_circuit_graph_enrichment(local_review) if local_review else None,
            entity_id=entity_id,
            user_id=user_id,
            enabled=True,
            decision_reason=decision_reason,
        )

    @staticmethod
    def _should_escalate_to_openai(local_review: dict[str, Any] | None) -> bool:
        if not local_review:
            return False
        confidence = optional_float(local_review.get("confidence")) or 0.0
        return bool(local_review.get("escalateToOpenAI")) or (bool(local_review.get("useful", True)) and confidence < 0.65)


def normalize_circuit_graph_enrichment(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {
        "provider": str(raw.get("provider") or ""),
        "model": raw.get("model"),
        "useful": bool(raw.get("useful", True)),
        "confidence": max(0.0, min(optional_float(raw.get("confidence")) or 0.0, 1.0)),
        "summary": _text(raw.get("summary"), 800),
        "proposedPins": _list_of_dicts(raw.get("proposedPins"), 80),
        "proposedNets": _list_of_dicts(raw.get("proposedNets"), 80),
        "proposedConnections": _list_of_dicts(raw.get("proposedConnections"), 120),
        "validationFindings": _normalize_findings(raw.get("validationFindings")),
        "escalateToOpenAI": bool(raw.get("escalateToOpenAI", False)),
        "reason": _text(raw.get("reason"), 600),
        "estimatedCost": raw.get("estimatedCost"),
        "paidBy": raw.get("paidBy"),
    }


def _normalize_findings(value: Any) -> list[dict[str, str]]:
    findings = []
    for item in value or []:
        if isinstance(item, dict):
            message = _text(item.get("message") or item.get("reason") or item.get("text"), 500)
            code = _text(item.get("code"), 80) or "ai_review"
            severity = _text(item.get("severity"), 40) or "warning"
        else:
            message = _text(item, 500)
            code = "ai_review"
            severity = "warning"
        if message:
            findings.append({"severity": severity, "code": code, "message": message})
    return findings[:80]


def _list_of_dicts(value: Any, limit: int) -> list[dict[str, Any]]:
    rows = []
    for item in value or []:
        if isinstance(item, dict):
            rows.append(dict(item))
    return rows[:limit]


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]
