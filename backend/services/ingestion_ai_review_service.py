from __future__ import annotations

import re
import time
from typing import Any, Callable

from backend.ingestion.document_classifier import detect_component_candidates, is_plausible_component
from backend.services.datasheet_repair_service import pinout_has_gaps
from backend.services.openai_assist_prompts import (
    LOCAL_INGESTION_REVIEW_SYSTEM_PROMPT,
    build_local_ingestion_review_prompt,
)
from backend.services.openai_assist_utils import parse_json_object


class IngestionAiReviewService:
    def __init__(
        self,
        *,
        config: dict,
        trace_logger: Any,
        ai_provider_store: Any,
        openai_assist_service: Any,
        query_local_llm: Callable[..., str] | None,
        local_model_name: str | None,
    ):
        self.config = config
        self.trace_logger = trace_logger
        self.ai_provider_store = ai_provider_store
        self.openai_assist_service = openai_assist_service
        self.query_local_llm = query_local_llm
        self.local_model_name = local_model_name

    def review(
        self,
        *,
        source_path: str,
        is_global: bool,
        entity_id: int | None,
        user_id: int | None,
        stats: dict[str, Any],
        sample_text: str,
        openai_enabled: bool,
        intelligence: dict[str, Any] | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> dict[str, Any] | None:
        decision = self.decision(source_path=source_path, stats=stats, sample_text=sample_text, intelligence=intelligence)
        if not decision["shouldReview"]:
            self.trace_logger.debug(f"🤖 Ingestion AI review skipped for {source_path}: {decision['reason']}")
            return None
        local_paid_by = self.local_paid_by(is_global=is_global, entity_id=entity_id)

        if progress_callback:
            progress_callback(documentPhase="Local AI review")
        local_review = self.run_local_review(
            source_path=source_path,
            stats=stats,
            sample_text=sample_text,
            deterministic_reasons=decision["reasons"],
        )
        if local_review:
            self.record_local_review(
                source_path,
                local_review,
                is_global=is_global,
                entity_id=entity_id,
                user_id=user_id,
                decision_reason=decision["reason"],
                paid_by=local_paid_by,
            )

        escalation_reason = self.escalation_reason(decision, local_review)
        if not openai_enabled:
            if local_review:
                self.trace_logger.info(
                    f"🤖 Local ingestion review completed for {source_path}; OpenAI escalation disabled."
                )
                return {
                    "provider": "ollama",
                    "model": self.local_model_name or "local",
                    "paidBy": local_paid_by,
                    "estimatedCost": 0.0,
                    "review": local_review,
                    "escalated": False,
                    "reason": escalation_reason or decision["reason"],
                }
            return None

        if not escalation_reason:
            if local_review:
                self.trace_logger.info(f"🤖 Local ingestion review accepted {source_path}; no OpenAI needed.")
                return {
                    "provider": "ollama",
                    "model": self.local_model_name or "local",
                    "paidBy": local_paid_by,
                    "estimatedCost": 0.0,
                    "review": local_review,
                    "escalated": False,
                    "reason": decision["reason"],
                }
            return None

        if progress_callback:
            progress_callback(documentPhase="OpenAI ingestion review")
        openai_result = self.openai_assist_service.review_ingestion(
            source_path=source_path,
            is_global=is_global,
            entity_id=entity_id,
            user_id=user_id,
            stats=stats,
            sample_text=sample_text,
            enabled=True,
            decision_reason=escalation_reason,
        )
        if openai_result:
            paid_by = openai_result.get("paidBy") or "unknown"
            self.trace_logger.info(f"🤖 OpenAI ingestion review used for {source_path}: {escalation_reason}")
            return {
                **openai_result,
                "provider": "ollama+openai" if local_review else "openai",
                "paidBy": paid_by,
                "localReview": local_review,
                "escalated": True,
                "reason": escalation_reason,
            }

        if local_review:
            self.trace_logger.info(
                f"🤖 Local ingestion review completed for {source_path}; OpenAI escalation was requested but unavailable."
            )
            return {
                "provider": "ollama",
                "model": self.local_model_name or "local",
                "paidBy": local_paid_by,
                "estimatedCost": 0.0,
                "review": local_review,
                "escalated": False,
                "reason": escalation_reason,
            }
        return None

    def decision(
        self,
        *,
        source_path: str,
        stats: dict[str, Any],
        sample_text: str,
        intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        text = sample_text or ""
        lowered = text.lower()
        basename = source_path.rsplit("/", 1)[-1]
        component_candidates = detect_component_candidates(basename, text[:4000])
        plausible_components = [
            candidate.value for candidate in component_candidates if is_plausible_component(candidate.value)
        ]
        datasheet_markers = (
            "datasheet",
            "data sheet",
            "pin configuration",
            "pin description",
            "pin functions",
            "terminal functions",
            "absolute maximum",
            "electrical characteristics",
        )
        if plausible_components:
            reasons.append(f"component candidate {plausible_components[0]}")
        if any(marker in lowered or marker in basename.lower() for marker in datasheet_markers):
            reasons.append("datasheet/pinout language detected")
        component_or_datasheet = bool(plausible_components) or any(
            marker in lowered or marker in basename.lower() for marker in datasheet_markers
        )

        chunk_count = int(stats.get("chunkCount") or 0)
        raw_chunks = int(stats.get("rawChunkCount") or 0)
        dropped_chunks = int(stats.get("droppedChunkCount") or max(raw_chunks - chunk_count, 0))
        images = int(stats.get("extractedImageCount") or 0)
        image_texts = int(stats.get("indexedImageTextCount") or 0)
        ocr_texts = int(stats.get("ocrImageTextCount") or 0)
        if raw_chunks and chunk_count == 0:
            reasons.append("all extracted text chunks were dropped")
        elif raw_chunks and dropped_chunks > max(10, raw_chunks * 0.25) and component_or_datasheet:
            reasons.append(f"component/datasheet extraction dropped {dropped_chunks} of {raw_chunks} raw chunks")
        if images >= 3 and image_texts == 0 and ocr_texts == 0:
            reasons.append("images were extracted but no OCR/image text was indexed")
        if len(text.strip()) < 800 and (images or raw_chunks) and component_or_datasheet:
            reasons.append("sample text is very short for extracted content")
        reasons.extend(self.intelligence_risk_reasons(intelligence))

        should_review = bool(reasons) and bool(self.config.get("INGEST_LOCAL_AI_REVIEW_ENABLED", True))
        return {
            "shouldReview": should_review,
            "reasons": reasons,
            "reason": "; ".join(reasons) if reasons else "no component/datasheet extraction risk detected",
        }

    @staticmethod
    def intelligence_risk_reasons(intelligence: dict[str, Any] | None) -> list[str]:
        if not intelligence or intelligence.get("documentType") != "component_datasheet":
            return []
        component_name = str(intelligence.get("componentName") or "").strip()
        if not component_name or not is_plausible_component(component_name):
            return []
        reasons: list[str] = []
        pins = (intelligence.get("pinout") or {}).get("pins") or []
        facts = intelligence.get("facts") or []
        if not pins:
            reasons.append(f"component datasheet {component_name} has no detected pinout")
        elif pinout_has_gaps(intelligence):
            reasons.append(f"component datasheet {component_name} has incomplete pin numbering")
        if len(facts) < 2:
            reasons.append(f"component datasheet {component_name} has only {len(facts)} extracted facts")
        try:
            confidence = float(intelligence.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence and confidence < 0.82:
            reasons.append(f"component datasheet {component_name} confidence {confidence:.2f} is low")
        return reasons

    def run_local_review(
        self,
        *,
        source_path: str,
        stats: dict[str, Any],
        sample_text: str,
        deterministic_reasons: list[str],
    ) -> dict[str, Any] | None:
        if not self.query_local_llm or not self.local_model_name:
            return None
        try:
            system_prompt = LOCAL_INGESTION_REVIEW_SYSTEM_PROMPT
            prompt = build_local_ingestion_review_prompt(
                source_path=source_path,
                stats=stats,
                sample_text=sample_text,
                deterministic_reasons=deterministic_reasons,
            )
            started_at = time.time()
            raw = self.query_local_llm(
                prompt,
                self.local_model_name,
                chat_history=[],
                system_prompt=system_prompt,
                gpu_priority=80,
                gpu_owner="ingest-ai",
                gpu_resource_class="local_llm",
                keep_alive=0,
            )
            parsed = parse_json_object(raw)
            review = normalize_local_review(parsed, raw)
            review["_inputTokenEstimate"] = estimate_local_tokens(system_prompt) + estimate_local_tokens(prompt)
            review["_outputTokenEstimate"] = estimate_local_tokens(raw)
            review["_latencyMs"] = int((time.time() - started_at) * 1000)
            return review
        except Exception as exc:
            self.trace_logger.warning(f"Local ingestion review failed for {source_path}: {exc}")
            return {
                "quality": "weak",
                "useful": False,
                "confidence": 0.0,
                "warnings": [f"local review failed: {str(exc)[:180]}"],
                "suggestedReviewFocus": "manual review",
                "escalateToOpenAI": True,
                "reason": "local ingestion review failed",
            }

    def record_local_review(
        self,
        source_path: str,
        review: dict[str, Any],
        *,
        is_global: bool,
        entity_id: int | None,
        user_id: int | None,
        decision_reason: str,
        paid_by: str,
    ) -> None:
        if not self.ai_provider_store:
            return
        try:
            input_tokens = int(review.get("_inputTokenEstimate") or 0)
            output_tokens = int(review.get("_outputTokenEstimate") or 0)
            latency_ms = int(review.get("_latencyMs") or 0)
            self.ai_provider_store.record_document_ingest_ai_review(
                source_path=source_path,
                provider="ollama",
                model_name=self.local_model_name or "local",
                paid_by=paid_by,
                review_text=review.get("raw") or "",
                review_json=review,
                estimated_cost=0.0,
            )
            if hasattr(self.ai_provider_store, "record_ai_assist_event"):
                self.ai_provider_store.record_ai_assist_event(
                    entity_id=None if is_global else entity_id,
                    user_id=user_id,
                    provider="ollama",
                    task_type="ingestion_assist",
                    model_name=self.local_model_name or "local",
                    context_type="document_ingest",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=0.0,
                    paid_by=paid_by,
                    success=True,
                    decision_reason=f"Local ingestion review ran for {source_path}: {decision_reason}",
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            self.trace_logger.debug(f"Local ingestion review audit skipped for {source_path}: {exc}")

    @staticmethod
    def escalation_reason(decision: dict[str, Any], local_review: dict[str, Any] | None) -> str | None:
        if not local_review:
            return f"Ingestion assist escalation for {decision['reason']}: local review unavailable."
        quality = str(local_review.get("quality") or "").lower()
        confidence = optional_float(local_review.get("confidence")) or 0.0
        if bool(local_review.get("escalateToOpenAI")):
            return f"Ingestion assist escalation for {decision['reason']}: {local_review.get('reason') or 'local review requested repair'}."
        if quality in {"poor", "weak"} and confidence < 0.75:
            return f"Ingestion assist escalation for {decision['reason']}: local quality={quality}, confidence={confidence:.2f}."
        if not bool(local_review.get("useful", True)):
            return f"Ingestion assist escalation for {decision['reason']}: local review marked extraction not useful."
        return None

    @staticmethod
    def local_paid_by(*, is_global: bool, entity_id: int | None) -> str:
        if is_global:
            return "system"
        if entity_id is not None:
            return "entity"
        return "unknown"


def normalize_local_review(parsed: dict[str, Any], raw: str) -> dict[str, Any]:
    if not isinstance(parsed, dict) or ("raw" in parsed and len(parsed) == 1):
        return {
            "quality": "weak",
            "useful": False,
            "confidence": 0.0,
            "warnings": ["local review did not return valid structured JSON"],
            "suggestedReviewFocus": "manual review",
            "escalateToOpenAI": True,
            "reason": "local review was not structured",
            "raw": str(raw or "")[:4000],
        }
    warnings = parsed.get("warnings")
    if not isinstance(warnings, list):
        warnings = [str(warnings)] if warnings else []
    quality = str(parsed.get("quality") or "usable").lower()
    if quality not in {"good", "usable", "weak", "poor"}:
        quality = "usable"
    return {
        "quality": quality,
        "useful": bool(parsed.get("useful", quality in {"good", "usable"})),
        "confidence": max(0.0, min(optional_float(parsed.get("confidence")) or 0.0, 1.0)),
        "warnings": [re.sub(r"\s+", " ", str(item)).strip()[:240] for item in warnings if str(item).strip()],
        "suggestedReviewFocus": re.sub(r"\s+", " ", str(parsed.get("suggestedReviewFocus") or "")).strip()[:240],
        "escalateToOpenAI": bool(parsed.get("escalateToOpenAI", False)),
        "reason": re.sub(r"\s+", " ", str(parsed.get("reason") or "")).strip()[:320],
        "raw": str(raw or "")[:4000],
    }


def optional_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def estimate_local_tokens(text: str | None) -> int:
    value = str(text or "")
    if not value:
        return 0
    return max(1, int(len(value) / 4))
