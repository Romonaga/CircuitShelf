from __future__ import annotations

import json
import time
from collections import OrderedDict
from typing import Any, Callable

from backend.services.circuit_build_recovery import parse_recovered_build_card
from backend.services.ingestion_ai_review_service import estimate_local_tokens, optional_float
from backend.services.openai_assist_prompts import (
    LOCAL_CONVERSATION_BENCH_PLAN_SYSTEM_PROMPT,
    build_conversation_bench_plan_prompt,
)
from backend.services.openai_assist_utils import parse_json_object


class ConversationBenchPlanService:
    def __init__(
        self,
        *,
        conversation_store: Any,
        assembly_plan_store: Any,
        ai_provider_store: Any,
        openai_assist_service: Any | None,
        query_local_llm: Callable[..., str] | None,
        local_model_name: str | None,
        trace_logger: Any = None,
    ):
        self.conversation_store = conversation_store
        self.assembly_plan_store = assembly_plan_store
        self.ai_provider_store = ai_provider_store
        self.openai_assist_service = openai_assist_service
        self.query_local_llm = query_local_llm
        self.local_model_name = local_model_name
        self.trace_logger = trace_logger

    def create_plan(
        self,
        *,
        conversation_id: str,
        user_id: int,
        username: str | None,
        entity_id: int | None,
        objective_override: str = "",
    ) -> dict[str, Any]:
        conversation = self.conversation_store.get(conversation_id, user_id)
        if not conversation:
            return {"ok": False, "status": 404, "error": "Conversation not found."}
        if not conversation.get("turns"):
            return {
                "ok": False,
                "status": 422,
                "error": "Conversation has no Ask turns to convert into a Bench plan.",
                "validation": _validation("no_conversation_turns", "Ask a concrete circuit question before creating a Bench project."),
            }

        objective = _objective_for_conversation(conversation, objective_override)
        source_payload = extract_source_payload(conversation)
        card, ai_review = self._card_from_existing_snapshot(conversation, source_payload)
        source = "conversation_build_card"
        if not card:
            local_review = self._run_local_synthesis(objective=objective, conversation=conversation, source_payload=source_payload)
            if local_review:
                self._record_local_event(
                    local_review,
                    conversation_id=conversation_id,
                    entity_id=entity_id,
                    user_id=user_id,
                    decision_reason=f"Local Ask-to-Bench synthesis ran for conversation {conversation_id}.",
                )
            card = self._card_from_ai_review(local_review, source_payload)
            ai_review = normalize_conversation_plan_review(local_review)
            source = "local_ai"
            if not card and self._should_escalate_to_openai(local_review):
                openai_review = self._run_openai_synthesis(
                    objective=objective,
                    conversation=conversation,
                    source_payload=source_payload,
                    local_review=ai_review,
                    entity_id=entity_id,
                    user_id=user_id,
                )
                card = self._card_from_ai_review(openai_review, source_payload)
                ai_review = normalize_conversation_plan_review(openai_review)
                source = "openai"

        if not card:
            return {
                "ok": False,
                "status": 422,
                "error": "Conversation does not contain enough grounded build detail for a Bench plan.",
                "aiReview": ai_review,
                "validation": _validation(
                    "bench_plan_not_grounded",
                    "Ask for exact parts, values, power, and pin-by-pin wiring or add sources before converting this conversation.",
                ),
            }

        card = ensure_conversation_card_warnings(card, source)
        plan = self.assembly_plan_store.create_from_card(
            question=objective,
            card=card,
            user_id=user_id,
            created_by=username,
        )
        return {
            "ok": True,
            "plan": plan,
            "source": source,
            "aiReview": ai_review,
            "validation": {
                "enabled": True,
                "ran": True,
                "useful": True,
                "changed": False,
                "confidence": card.get("confidence"),
                "issues": card.get("warnings") or [],
                "notes": [f"Bench plan created from Ask conversation {conversation_id}."],
                "elapsedMs": 0,
                "model": ai_review.get("model") if isinstance(ai_review, dict) else None,
            },
        }

    def _card_from_existing_snapshot(self, conversation: dict[str, Any], source_payload: list[dict[str, Any]]) -> tuple[dict | None, dict | None]:
        for turn in reversed(conversation.get("turns") or []):
            snapshot = turn.get("responseSnapshot") or {}
            build_card = snapshot.get("buildCard")
            if isinstance(build_card, dict):
                card = parse_recovered_build_card(json.dumps(build_card), source_payload)
                if card:
                    return card, {
                        "provider": "snapshot",
                        "useful": True,
                        "confidence": card.get("confidence"),
                        "summary": "Used build card already produced by Ask.",
                        "reason": "conversation snapshot contained a valid build card",
                    }
        return None, None

    def _run_local_synthesis(
        self,
        *,
        objective: str,
        conversation: dict[str, Any],
        source_payload: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not self.query_local_llm or not self.local_model_name:
            return None
        system_prompt = LOCAL_CONVERSATION_BENCH_PLAN_SYSTEM_PROMPT
        prompt = build_conversation_bench_plan_prompt(
            objective=objective,
            conversation=conversation,
            source_payload=source_payload,
        )
        started_at = time.time()
        try:
            raw = self.query_local_llm(
                prompt,
                self.local_model_name,
                chat_history=[],
                system_prompt=system_prompt,
                gpu_priority=85,
                gpu_owner="ask-to-bench",
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
                self.trace_logger.warning(f"Local Ask-to-Bench synthesis failed: {exc}")
            return {
                "useful": False,
                "confidence": 0.0,
                "warnings": ["Local AI could not synthesize a Bench plan."],
                "escalateToOpenAI": True,
                "reason": "local Ask-to-Bench synthesis failed",
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
        conversation_id: str,
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
            task_type="assembly_plan",
            model_name=self.local_model_name or "local",
            context_type="conversation_to_bench",
            context_id=conversation_id,
            input_tokens=int(result.get("_inputTokenEstimate") or 0),
            output_tokens=int(result.get("_outputTokenEstimate") or 0),
            estimated_cost=0.0,
            paid_by=paid_by,
            success=bool(result.get("_success", True)),
            error_message=result.get("_errorMessage"),
            decision_reason=decision_reason,
            latency_ms=int(result.get("_latencyMs") or 0),
        )

    def _run_openai_synthesis(
        self,
        *,
        objective: str,
        conversation: dict[str, Any],
        source_payload: list[dict[str, Any]],
        local_review: dict[str, Any] | None,
        entity_id: int | None,
        user_id: int | None,
    ) -> dict[str, Any] | None:
        if not self.openai_assist_service or not hasattr(self.openai_assist_service, "synthesize_conversation_bench_plan"):
            return None
        return self.openai_assist_service.synthesize_conversation_bench_plan(
            objective=objective,
            conversation=conversation,
            source_payload=source_payload,
            local_review=local_review,
            entity_id=entity_id,
            user_id=user_id,
            enabled=True,
            decision_reason="Local Ask-to-Bench synthesis could not produce a grounded plan.",
        )

    def _card_from_ai_review(self, review: dict[str, Any] | None, source_payload: list[dict[str, Any]]) -> dict | None:
        if not isinstance(review, dict) or review.get("useful") is False:
            return None
        return parse_recovered_build_card(json.dumps(review), source_payload)

    @staticmethod
    def _should_escalate_to_openai(local_review: dict[str, Any] | None) -> bool:
        if not local_review:
            return False
        confidence = optional_float(local_review.get("confidence")) or 0.0
        return bool(local_review.get("escalateToOpenAI")) or (bool(local_review.get("useful", True)) and confidence < 0.65)


def extract_source_payload(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    sources: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for turn in conversation.get("turns") or []:
        snapshot = turn.get("responseSnapshot") or {}
        for source in snapshot.get("sources") or []:
            key = str(source.get("source") or source.get("displayName") or "")
            if not key:
                continue
            existing = sources.get(key)
            if not existing:
                sources[key] = {
                    "source": source.get("source") or key,
                    "displayName": source.get("displayName") or key,
                    "pages": [],
                    "chunkCount": int(source.get("chunkCount") or source.get("chunks") or 0),
                    "chunks": [],
                }
                existing = sources[key]
            for page in source.get("pages") or []:
                try:
                    page_number = int(page)
                except (TypeError, ValueError):
                    continue
                if page_number > 0 and page_number not in existing["pages"]:
                    existing["pages"].append(page_number)
            for chunk in source.get("chunks") or []:
                if isinstance(chunk, dict) and len(existing["chunks"]) < 6:
                    existing["chunks"].append(chunk)
            existing["chunkCount"] = max(existing["chunkCount"], int(source.get("chunkCount") or source.get("chunks") or 0))
    return list(sources.values())


def ensure_conversation_card_warnings(card: dict[str, Any], source: str) -> dict[str, Any]:
    card = dict(card)
    warnings = list(card.get("warnings") or [])
    if source != "conversation_build_card":
        warnings.append("Generated from Ask conversation; verify source evidence before powering the circuit.")
    if len(card.get("wiring") or []) < 2:
        warnings.append("Bench plan has limited wiring detail; ask for pin-by-pin steps before building.")
    card["warnings"] = _dedupe_strings(warnings)
    return card


def normalize_conversation_plan_review(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {
        "provider": str(raw.get("provider") or ""),
        "model": raw.get("model"),
        "useful": bool(raw.get("useful", True)),
        "confidence": max(0.0, min(optional_float(raw.get("confidence")) or 0.0, 1.0)),
        "summary": str(raw.get("summary") or "")[:800],
        "warnings": [str(item)[:500] for item in (raw.get("warnings") or [])[:20]],
        "escalateToOpenAI": bool(raw.get("escalateToOpenAI", False)),
        "reason": str(raw.get("reason") or "")[:600],
        "estimatedCost": raw.get("estimatedCost"),
        "paidBy": raw.get("paidBy"),
    }


def _objective_for_conversation(conversation: dict[str, Any], objective_override: str) -> str:
    cleaned = " ".join(str(objective_override or "").split())
    if cleaned:
        return cleaned[:600]
    turns = conversation.get("turns") or []
    for turn in reversed(turns):
        question = " ".join(str(turn.get("question") or "").split())
        if question:
            return question[:600]
    return str(conversation.get("title") or "Ask conversation Bench project")[:600]


def _validation(code: str, message: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "ran": True,
        "useful": False,
        "changed": False,
        "confidence": 0.0,
        "issues": [code],
        "notes": [message],
        "elapsedMs": 0,
        "model": None,
    }


def _dedupe_strings(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        text = " ".join(str(item or "").split())
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result[:12]
