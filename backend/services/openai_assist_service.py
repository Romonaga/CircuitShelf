from __future__ import annotations

import time
from typing import Any

import requests

from response_finalizer import (
    ResponseValidationResult,
    build_response_finalizer_prompt,
    deterministic_response_issues,
    parse_response_finalizer_output,
    should_run_response_finalizer,
)


class OpenAIAssistService:
    def __init__(self, ai_provider_store: Any, logger: Any = None, *, timeout_seconds: int = 90):
        self.ai_provider_store = ai_provider_store
        self.logger = logger
        self.timeout_seconds = timeout_seconds

    def finalize_response(
        self,
        *,
        question: str,
        answer: str,
        source_payload: list[dict],
        build_card: dict | None,
        local_model_name: str,
        confidence: Any,
        enabled: bool,
        mode: str,
        min_confidence: float,
        max_context_chars: int,
        entity_id: int | None,
        user_id: int | None,
        context_type: str = "",
        context_id: str | None = None,
    ) -> tuple[str, ResponseValidationResult] | None:
        settings = self.ai_provider_store.resolve_openai_assist(entity_id=entity_id, user_id=user_id)
        if not enabled or not settings or not settings.get("apiKey"):
            return None

        provider_mode = str(settings.get("assistMode") or "auto").lower()
        if provider_mode == "off":
            return None
        effective_mode = "always" if provider_mode == "always" else mode
        issues = deterministic_response_issues(question, answer, source_payload, build_card)
        if not should_run_response_finalizer(
            enabled=enabled,
            mode=effective_mode,
            confidence=confidence,
            build_card=build_card,
            issues=issues,
            min_confidence=min_confidence,
        ):
            return None

        prompt = build_response_finalizer_prompt(
            question=question,
            answer=answer,
            source_payload=source_payload,
            build_card=build_card,
            deterministic_issues=issues,
            max_context_chars=max_context_chars,
        )
        started_at = time.time()
        event_base = {
            "entity_id": entity_id,
            "user_id": user_id,
            "provider": "openai",
            "task_type": "answer_validation",
            "model_name": settings["modelName"],
            "context_type": context_type,
            "context_id": context_id,
            "round_number": 1,
            "round_count": 1,
            "paid_by": settings["paidBy"],
            "provider_key_owner_user_id": settings.get("providerKeyOwnerUserId"),
        }
        try:
            data = self._create_response(
                api_key=settings["apiKey"],
                model=settings["modelName"],
                instructions=(
                    "You are CircuitShelf's OpenAI answer validator. Return only the requested JSON. "
                    "Do not add unsupported electronics facts or component values."
                ),
                input_text=prompt,
                max_output_tokens=1600,
            )
            text = extract_response_text(data)
            usage = extract_usage(data)
            estimated_cost = self.ai_provider_store.estimate_cost(
                provider="openai",
                model_name=settings["modelName"],
                input_tokens=usage["inputTokens"],
                cached_input_tokens=usage["cachedInputTokens"],
                output_tokens=usage["outputTokens"],
            )
            self.ai_provider_store.record_ai_assist_event(
                **event_base,
                input_tokens=usage["inputTokens"],
                cached_input_tokens=usage["cachedInputTokens"],
                output_tokens=usage["outputTokens"],
                estimated_cost=estimated_cost,
                success=True,
            )
            revised, result = parse_response_finalizer_output(text, fallback_answer=answer, deterministic_issues=issues)
            result.elapsed_ms = int((time.time() - started_at) * 1000)
            result.model = f"openai:{settings['modelName']}"
            result.notes = [*result.notes, f"OpenAI assist cost ${estimated_cost:.6f}."]
            return revised, result
        except Exception as exc:
            message = safe_error_message(exc)
            self.ai_provider_store.record_ai_assist_event(
                **event_base,
                input_tokens=0,
                cached_input_tokens=0,
                output_tokens=0,
                estimated_cost=0,
                success=False,
                error_message=message,
            )
            if self.logger:
                self.logger.warning(f"OpenAI assist finalizer failed: {message}")
            return None

    def answer_without_sources(
        self,
        *,
        question: str,
        entity_id: int | None,
        user_id: int | None,
        context_type: str = "",
        context_id: str | None = None,
    ) -> tuple[str, dict[str, Any]] | None:
        settings = self.ai_provider_store.resolve_openai_assist(entity_id=entity_id, user_id=user_id)
        if not settings or not settings.get("apiKey") or settings.get("assistMode") == "off":
            return None
        prompt = (
            "CircuitShelf could not find matching indexed documents for this electronics question.\n"
            "Answer from general electronics knowledge only if you can do so safely. Begin by saying "
            "that no indexed source matched. If the request needs a datasheet, exact pinout, mains wiring, "
            "or safety-critical values, say what must be verified instead of guessing.\n\n"
            f"Question: {question}"
        )
        event_base = {
            "entity_id": entity_id,
            "user_id": user_id,
            "provider": "openai",
            "task_type": "answer_validation",
            "model_name": settings["modelName"],
            "context_type": context_type,
            "context_id": context_id,
            "round_number": 1,
            "round_count": 1,
            "paid_by": settings["paidBy"],
            "provider_key_owner_user_id": settings.get("providerKeyOwnerUserId"),
        }
        started_at = time.time()
        try:
            data = self._create_response(
                api_key=settings["apiKey"],
                model=settings["modelName"],
                instructions="You are CircuitShelf's electronics fallback assistant. Be concise, practical, and explicit about missing source grounding.",
                input_text=prompt,
                max_output_tokens=1200,
            )
            usage = extract_usage(data)
            estimated_cost = self.ai_provider_store.estimate_cost(
                provider="openai",
                model_name=settings["modelName"],
                input_tokens=usage["inputTokens"],
                cached_input_tokens=usage["cachedInputTokens"],
                output_tokens=usage["outputTokens"],
            )
            self.ai_provider_store.record_ai_assist_event(
                **event_base,
                input_tokens=usage["inputTokens"],
                cached_input_tokens=usage["cachedInputTokens"],
                output_tokens=usage["outputTokens"],
                estimated_cost=estimated_cost,
                success=True,
            )
            return extract_response_text(data), {
                "enabled": True,
                "ran": True,
                "useful": True,
                "changed": True,
                "confidence": None,
                "issues": ["No indexed documents matched this question."],
                "notes": [f"Answered with OpenAI fallback. Estimated cost ${estimated_cost:.6f}."],
                "elapsedMs": int((time.time() - started_at) * 1000),
                "model": f"openai:{settings['modelName']}",
            }
        except Exception as exc:
            message = safe_error_message(exc)
            self.ai_provider_store.record_ai_assist_event(
                **event_base,
                input_tokens=0,
                cached_input_tokens=0,
                output_tokens=0,
                estimated_cost=0,
                success=False,
                error_message=message,
            )
            if self.logger:
                self.logger.warning(f"OpenAI fallback answer failed: {message}")
            return None

    def _create_response(
        self,
        *,
        api_key: str,
        model: str,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "instructions": instructions,
                "input": input_text,
                "max_output_tokens": max_output_tokens,
                "store": False,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def extract_response_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return str(data["output_text"])
    parts: list[str] = []
    for item in data.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts).strip()


def extract_usage(data: dict[str, Any]) -> dict[str, int]:
    usage = data.get("usage") or {}
    input_details = usage.get("input_tokens_details") or {}
    return {
        "inputTokens": int(usage.get("input_tokens") or 0),
        "cachedInputTokens": int(input_details.get("cached_tokens") or 0),
        "outputTokens": int(usage.get("output_tokens") or 0),
    }


def safe_error_message(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            payload = exc.response.json()
            detail = payload.get("error", {}).get("message") or payload.get("error")
            if detail:
                return str(detail)[:1000]
        except Exception:
            pass
        return f"OpenAI HTTP {exc.response.status_code}"
    return str(exc)[:1000]
