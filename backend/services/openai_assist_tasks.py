from __future__ import annotations

import time
from typing import Any

from backend.services.openai_assist_accounting import OpenAIAssistAccountingMixin
from backend.services.openai_assist_prompts import (
    ANSWER_VALIDATION_INSTRUCTIONS,
    DATASHEET_REPAIR_INSTRUCTIONS,
    FALLBACK_ANSWER_INSTRUCTIONS,
    INGESTION_REVIEW_INSTRUCTIONS,
    INVENTORY_PHOTO_INSTRUCTIONS,
    build_datasheet_repair_prompt,
    build_fallback_answer_prompt,
    build_ingestion_review_prompt,
    build_inventory_photo_prompt,
)
from backend.services.openai_assist_utils import parse_json_object
from backend.services.openai_response_client import (
    OpenAIResponseClient,
    extract_response_text,
    extract_usage,
    safe_error_message,
)
from backend.services.response_finalizer import (
    ResponseValidationResult,
    build_response_finalizer_prompt,
    deterministic_response_issues,
    parse_response_finalizer_output,
    should_run_response_finalizer,
)


class OpenAIAssistTaskRunner(OpenAIAssistAccountingMixin):
    def __init__(self, ai_provider_store: Any, logger: Any = None, *, timeout_seconds: int = 90):
        self.ai_provider_store = ai_provider_store
        self.logger = logger
        self.response_client = OpenAIResponseClient(timeout_seconds=timeout_seconds)

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
        decision_reason = finalizer_decision_reason(
            provider_mode=provider_mode,
            effective_mode=effective_mode,
            confidence=confidence,
            min_confidence=min_confidence,
            build_card=build_card,
            issues=issues,
        )

        prompt = build_response_finalizer_prompt(
            question=question,
            answer=answer,
            source_payload=source_payload,
            build_card=build_card,
            deterministic_issues=issues,
            max_context_chars=max_context_chars,
        )
        started_at = time.time()
        event_base = self._assist_event_base(
            settings=settings,
            entity_id=entity_id,
            user_id=user_id,
            task_type="answer_validation",
            context_type=context_type,
            context_id=context_id,
            decision_reason=decision_reason,
        )
        if self._record_budget_block_if_needed(event_base, settings):
            return None
        try:
            data = self._create_response(
                api_key=settings["apiKey"],
                model=settings["modelName"],
                instructions=ANSWER_VALIDATION_INSTRUCTIONS,
                input_text=prompt,
                max_output_tokens=1600,
            )
            text = extract_response_text(data)
            usage = extract_usage(data)
            estimated_cost = self._estimate_openai_cost(settings, usage)
            elapsed_ms = int((time.time() - started_at) * 1000)
            self._record_ai_success(event_base, usage, estimated_cost, latency_ms=elapsed_ms)
            revised, result = parse_response_finalizer_output(text, fallback_answer=answer, deterministic_issues=issues)
            result.elapsed_ms = elapsed_ms
            result.model = f"openai:{settings['modelName']}"
            result.notes = [*result.notes, f"OpenAI assist cost ${estimated_cost:.6f}."]
            return revised, result
        except Exception as exc:
            message = safe_error_message(exc)
            self._record_ai_failure(event_base, message, latency_ms=int((time.time() - started_at) * 1000))
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
        event_base = self._assist_event_base(
            settings=settings,
            entity_id=entity_id,
            user_id=user_id,
            task_type="answer_validation",
            context_type=context_type,
            context_id=context_id,
            decision_reason="No relevant indexed documents were found, so OpenAI fallback answered without local RAG sources.",
        )
        if self._record_budget_block_if_needed(event_base, settings):
            return None
        started_at = time.time()
        try:
            data = self._create_response(
                api_key=settings["apiKey"],
                model=settings["modelName"],
                instructions=FALLBACK_ANSWER_INSTRUCTIONS,
                input_text=build_fallback_answer_prompt(question),
                max_output_tokens=1200,
            )
            usage = extract_usage(data)
            estimated_cost = self._estimate_openai_cost(settings, usage)
            elapsed_ms = int((time.time() - started_at) * 1000)
            self._record_ai_success(event_base, usage, estimated_cost, latency_ms=elapsed_ms)
            return extract_response_text(data), {
                "enabled": True,
                "ran": True,
                "useful": True,
                "changed": True,
                "confidence": None,
                "issues": ["No indexed documents matched this question."],
                "notes": [f"Answered with OpenAI fallback. Estimated cost ${estimated_cost:.6f}."],
                "elapsedMs": elapsed_ms,
                "model": f"openai:{settings['modelName']}",
            }
        except Exception as exc:
            message = safe_error_message(exc)
            self._record_ai_failure(event_base, message, latency_ms=int((time.time() - started_at) * 1000))
            if self.logger:
                self.logger.warning(f"OpenAI fallback answer failed: {message}")
            return None

    def review_ingestion(
        self,
        *,
        source_path: str,
        is_global: bool,
        entity_id: int | None,
        user_id: int | None,
        stats: dict[str, Any],
        sample_text: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        if not enabled:
            return None
        settings = self.ai_provider_store.resolve_openai_ingestion_assist(
            is_global=is_global,
            entity_id=entity_id,
            user_id=user_id,
        )
        if not settings or not settings.get("apiKey") or settings.get("assistMode") == "off":
            return None

        event_base = self._assist_event_base(
            settings=settings,
            entity_id=None if is_global else entity_id,
            user_id=user_id,
            task_type="ingestion_assist",
            context_type="document_ingest",
            decision_reason=f"Ingestion review enabled for {source_path}; sampled chunks and extraction stats were sent for quality review.",
        )
        if self._record_budget_block_if_needed(event_base, settings):
            return None
        started_at = time.time()
        try:
            data = self._create_response(
                api_key=settings["apiKey"],
                model=settings["modelName"],
                instructions=INGESTION_REVIEW_INSTRUCTIONS,
                input_text=build_ingestion_review_prompt(
                    source_path=source_path,
                    is_global=is_global,
                    stats=stats,
                    sample_text=sample_text,
                ),
                max_output_tokens=700,
            )
            usage = extract_usage(data)
            estimated_cost = self._estimate_openai_cost(settings, usage)
            text = extract_response_text(data)
            parsed = parse_json_object(text)
            self._record_ai_success(event_base, usage, estimated_cost, latency_ms=int((time.time() - started_at) * 1000))
            self.ai_provider_store.record_document_ingest_ai_review(
                source_path=source_path,
                provider="openai",
                model_name=settings["modelName"],
                paid_by=settings["paidBy"],
                review_text=text,
                review_json=parsed,
                estimated_cost=estimated_cost,
            )
            return {
                "provider": "openai",
                "model": settings["modelName"],
                "paidBy": settings["paidBy"],
                "estimatedCost": estimated_cost,
                "review": parsed,
            }
        except Exception as exc:
            message = safe_error_message(exc)
            self._record_ai_failure(event_base, message, latency_ms=int((time.time() - started_at) * 1000))
            if self.logger:
                self.logger.warning(f"OpenAI ingestion assist failed for {source_path}: {message}")
            return None

    def repair_datasheet_intelligence(
        self,
        *,
        source_path: str,
        is_global: bool,
        entity_id: int | None,
        user_id: int | None,
        local_intelligence: dict[str, Any],
        sample_text: str,
        enabled: bool,
        decision_reason: str = "",
    ) -> dict[str, Any] | None:
        if not enabled:
            return None
        settings = self.ai_provider_store.resolve_openai_ingestion_assist(
            is_global=is_global,
            entity_id=entity_id,
            user_id=user_id,
        )
        if not settings or not settings.get("apiKey") or settings.get("assistMode") == "off":
            return None

        event_base = self._assist_event_base(
            settings=settings,
            entity_id=None if is_global else entity_id,
            user_id=user_id,
            task_type="ingestion_assist",
            context_type="datasheet_intelligence",
            decision_reason=decision_reason or f"Datasheet intelligence repair requested for {source_path}.",
        )
        if self._record_budget_block_if_needed(event_base, settings):
            return None
        started_at = time.time()
        try:
            data = self._create_response(
                api_key=settings["apiKey"],
                model=settings["modelName"],
                instructions=DATASHEET_REPAIR_INSTRUCTIONS,
                input_text=build_datasheet_repair_prompt(
                    source_path=source_path,
                    is_global=is_global,
                    local_intelligence=local_intelligence,
                    sample_text=sample_text,
                ),
                max_output_tokens=1800,
            )
            usage = extract_usage(data)
            estimated_cost = self._estimate_openai_cost(settings, usage)
            text = extract_response_text(data)
            parsed = parse_json_object(text)
            self._record_ai_success(event_base, usage, estimated_cost, latency_ms=int((time.time() - started_at) * 1000))
            self.ai_provider_store.record_document_ingest_ai_review(
                source_path=source_path,
                provider="openai",
                model_name=settings["modelName"],
                paid_by=settings["paidBy"],
                review_text=text,
                review_json={
                    "kind": "datasheet_intelligence_repair",
                    "repair": parsed,
                    "localConfidence": local_intelligence.get("confidence"),
                    "decisionReason": event_base["decision_reason"],
                },
                estimated_cost=estimated_cost,
            )
            return {
                "provider": "openai",
                "model": settings["modelName"],
                "paidBy": settings["paidBy"],
                "estimatedCost": estimated_cost,
                "repair": parsed,
            }
        except Exception as exc:
            message = safe_error_message(exc)
            self._record_ai_failure(event_base, message, latency_ms=int((time.time() - started_at) * 1000))
            if self.logger:
                self.logger.warning(f"OpenAI datasheet intelligence repair failed for {source_path}: {message}")
            return None

    def identify_inventory_photo(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        note: str,
        entity_id: int | None,
        user_id: int | None,
    ) -> dict[str, Any] | None:
        settings = self.ai_provider_store.resolve_openai_assist(entity_id=entity_id, user_id=user_id)
        if not settings or not settings.get("apiKey") or settings.get("assistMode") == "off":
            return None
        event_base = self._assist_event_base(
            settings=settings,
            entity_id=entity_id,
            user_id=user_id,
            task_type="inventory_photo_import",
            context_type="inventory_import",
            decision_reason="User requested inventory import from a photo.",
        )
        budget_block = self._record_budget_block_if_needed(event_base, settings)
        if budget_block:
            raise ValueError(budget_block)

        started_at = time.time()
        try:
            data = self._create_multimodal_response(
                api_key=settings["apiKey"],
                model=settings["modelName"],
                instructions=INVENTORY_PHOTO_INSTRUCTIONS,
                input_text=build_inventory_photo_prompt(note),
                image_bytes=image_bytes,
                mime_type=mime_type,
                max_output_tokens=1400,
            )
            usage = extract_usage(data)
            estimated_cost = self._estimate_openai_cost(settings, usage)
            self._record_ai_success(event_base, usage, estimated_cost, latency_ms=int((time.time() - started_at) * 1000))
            parsed = parse_json_object(extract_response_text(data))
            parsed["estimatedCost"] = estimated_cost
            parsed["model"] = settings["modelName"]
            parsed["paidBy"] = settings["paidBy"]
            return parsed
        except ValueError:
            raise
        except Exception as exc:
            message = safe_error_message(exc)
            self._record_ai_failure(event_base, message, latency_ms=int((time.time() - started_at) * 1000))
            if self.logger:
                self.logger.warning(f"OpenAI inventory photo import failed: {message}")
            raise ValueError(f"Inventory photo analysis failed: {message}") from exc

    def _create_response(
        self,
        *,
        api_key: str,
        model: str,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        return self.response_client.create_response(
            api_key=api_key,
            model=model,
            instructions=instructions,
            input_text=input_text,
            max_output_tokens=max_output_tokens,
        )

    def _create_multimodal_response(
        self,
        *,
        api_key: str,
        model: str,
        instructions: str,
        input_text: str,
        image_bytes: bytes,
        mime_type: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        return self.response_client.create_multimodal_response(
            api_key=api_key,
            model=model,
            instructions=instructions,
            input_text=input_text,
            image_bytes=image_bytes,
            mime_type=mime_type,
            max_output_tokens=max_output_tokens,
        )


def finalizer_decision_reason(
    *,
    provider_mode: str,
    effective_mode: str,
    confidence: Any,
    min_confidence: float,
    build_card: dict | None,
    issues: list[str],
) -> str:
    reasons: list[str] = []
    if provider_mode == "always" or effective_mode == "always":
        reasons.append("validation mode is always")
    if issues:
        reasons.append(f"deterministic issues: {', '.join(str(issue) for issue in issues[:3])}")
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = None
    if confidence_value is not None and confidence_value < min_confidence:
        reasons.append(f"retrieval confidence {confidence_value:.2f} is below {min_confidence:.2f}")
    if build_card:
        reasons.append("answer included a build card")
    if not reasons:
        reasons.append(f"validation mode {effective_mode} allowed OpenAI answer validation")
    return "; ".join(reasons)[:1000]
