from __future__ import annotations

import time
from typing import Any, Callable

from backend.services.openai_assist_prompts import (
    LOCAL_PROJECT_FINDER_TRIAGE_SYSTEM_PROMPT,
    build_project_finder_triage_prompt,
)
from backend.services.openai_assist_utils import parse_json_object
from backend.services.ingestion_ai_review_service import estimate_local_tokens, optional_float


class ProjectFinderAiTriageService:
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

    def triage_response(self, response: dict[str, Any], *, entity_id: int | None, user_id: int | None) -> dict[str, Any]:
        if not bool(self.config.get("PROJECT_FINDER_AI_TRIAGE_ENABLED", True)):
            response["aiTriage"] = {"enabled": False, "reviewedCount": 0}
            return response
        candidates = self._select_candidates(response.get("candidates") or [])
        if not candidates:
            response["aiTriage"] = {"enabled": True, "reviewedCount": 0}
            return response

        decision_reason = self._decision_reason(candidates)
        local_result = self._run_local_triage(candidates, decision_reason)
        if local_result:
            self._record_local_event(
                local_result,
                entity_id=entity_id,
                user_id=user_id,
                decision_reason=decision_reason,
            )
            self._apply_reviews(
                response,
                normalize_project_finder_reviews(local_result),
                provider="ollama",
                model=self.local_model_name or "local",
                escalated=False,
            )

        openai_candidates = self._openai_escalation_candidates(candidates, local_result)
        openai_result = None
        if openai_candidates and bool(self.config.get("PROJECT_FINDER_OPENAI_TRIAGE_ENABLED", True)):
            openai_result = self.openai_assist_service.triage_project_finder(
                candidates=openai_candidates,
                entity_id=entity_id,
                user_id=user_id,
                enabled=True,
                decision_reason=f"{decision_reason}; local triage left {len(openai_candidates)} candidate(s) low confidence.",
            )
            if openai_result:
                self._apply_reviews(
                    response,
                    normalize_project_finder_reviews(openai_result),
                    provider="ollama+openai" if local_result else "openai",
                    model=openai_result.get("model") or "openai",
                    escalated=True,
                )

        response["aiTriage"] = {
            "enabled": True,
            "reviewedCount": len(candidates),
            "localReviewedCount": len(candidates) if local_result else 0,
            "openaiReviewedCount": len(openai_candidates) if openai_result else 0,
            "escalated": bool(openai_result),
        }
        return response

    def _select_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        max_candidates = max(1, int(self.config.get("PROJECT_FINDER_AI_MAX_CANDIDATES", 4)))
        min_score = float(self.config.get("PROJECT_FINDER_AI_LOW_SCORE_THRESHOLD", 80))
        selected = []
        for candidate in candidates:
            score = optional_float(candidate.get("score")) or 0.0
            ambiguous = bool(candidate.get("rejectionReasons")) or not bool(candidate.get("projectLike", True))
            if score < min_score or ambiguous:
                selected.append(candidate)
            if len(selected) >= max_candidates:
                break
        return selected

    @staticmethod
    def _decision_reason(candidates: list[dict[str, Any]]) -> str:
        ids = ", ".join(str(candidate.get("id")) for candidate in candidates[:6])
        return f"Project Finder local triage reviewed low-score or ambiguous candidates: {ids}."

    def _run_local_triage(self, candidates: list[dict[str, Any]], decision_reason: str) -> dict[str, Any] | None:
        if not self.query_local_llm or not self.local_model_name:
            return None
        system_prompt = LOCAL_PROJECT_FINDER_TRIAGE_SYSTEM_PROMPT
        prompt = build_project_finder_triage_prompt(candidates=candidates, deterministic_reason=decision_reason)
        started_at = time.time()
        try:
            raw = self.query_local_llm(
                prompt,
                self.local_model_name,
                chat_history=[],
                system_prompt=system_prompt,
                gpu_priority=85,
                gpu_owner="project-finder-ai",
                gpu_resource_class="local_llm",
                keep_alive=0,
            )
            parsed = parse_json_object(raw)
            parsed["raw"] = str(raw or "")[:4000]
            parsed["_inputTokenEstimate"] = estimate_local_tokens(system_prompt) + estimate_local_tokens(prompt)
            parsed["_outputTokenEstimate"] = estimate_local_tokens(raw)
            parsed["_latencyMs"] = int((time.time() - started_at) * 1000)
            parsed["_success"] = True
            return parsed
        except Exception as exc:
            if self.trace_logger:
                self.trace_logger.warning(f"Local Project Finder triage failed: {exc}")
            return {
                "candidates": [
                    {
                        "id": candidate.get("id"),
                        "useful": False,
                        "confidence": 0.0,
                        "recommendedAction": "manual_review",
                        "notes": ["local Project Finder triage failed"],
                        "escalateToOpenAI": True,
                        "reason": "local Project Finder triage failed",
                    }
                    for candidate in candidates
                ],
                "raw": "",
                "_inputTokenEstimate": 0,
                "_outputTokenEstimate": 0,
                "_latencyMs": int((time.time() - started_at) * 1000),
                "_success": False,
                "_errorMessage": f"local Project Finder triage failed: {str(exc)[:240]}",
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
            task_type="project_finder",
            model_name=self.local_model_name or "local",
            context_type="project_finder",
            input_tokens=int(result.get("_inputTokenEstimate") or 0),
            output_tokens=int(result.get("_outputTokenEstimate") or 0),
            estimated_cost=0.0,
            paid_by=paid_by,
            success=bool(result.get("_success", True)),
            error_message=result.get("_errorMessage"),
            decision_reason=decision_reason,
            latency_ms=int(result.get("_latencyMs") or 0),
        )

    def _openai_escalation_candidates(
        self,
        candidates: list[dict[str, Any]],
        local_result: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if not local_result:
            return []
        confidence_threshold = float(self.config.get("PROJECT_FINDER_OPENAI_MIN_LOCAL_CONFIDENCE", 0.7))
        reviews = {review["id"]: review for review in normalize_project_finder_reviews(local_result)}
        selected = []
        for candidate in candidates:
            review = reviews.get(str(candidate.get("id")))
            if not review:
                continue
            confidence = optional_float(review.get("confidence")) or 0.0
            if bool(review.get("escalateToOpenAI")) or (confidence < confidence_threshold and bool(review.get("useful", True))):
                selected.append(candidate)
        return selected

    @staticmethod
    def _apply_reviews(
        response: dict[str, Any],
        reviews: list[dict[str, Any]],
        *,
        provider: str,
        model: str,
        escalated: bool,
    ) -> None:
        by_id = {review["id"]: review for review in reviews}
        for candidate in response.get("candidates") or []:
            review = by_id.get(str(candidate.get("id")))
            if not review:
                continue
            reason = review.get("reason") or "AI triage reviewed this candidate."
            confidence = optional_float(review.get("confidence")) or 0.0
            note = f"AI triage ({provider}, confidence {confidence:.2f}): {reason}"
            if bool(review.get("useful", True)):
                candidate.setdefault("matchReasons", []).append(note)
            else:
                candidate.setdefault("rejectionReasons", []).append(note)
            candidate["aiTriage"] = {
                "provider": provider,
                "model": model,
                "confidence": confidence,
                "useful": bool(review.get("useful", True)),
                "recommendedAction": review.get("recommendedAction") or "manual_review",
                "notes": review.get("notes") or [],
                "reason": reason,
                "escalated": escalated,
            }


def normalize_project_finder_reviews(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw_reviews = (payload or {}).get("candidates") or []
    if not isinstance(raw_reviews, list):
        return []
    reviews = []
    for item in raw_reviews:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        notes = item.get("notes")
        if not isinstance(notes, list):
            notes = [str(notes)] if notes else []
        action = str(item.get("recommendedAction") or "manual_review").strip().lower()
        if action not in {"keep", "demote", "needs_parts", "manual_review"}:
            action = "manual_review"
        reviews.append(
            {
                "id": str(item.get("id")),
                "useful": bool(item.get("useful", True)),
                "confidence": max(0.0, min(optional_float(item.get("confidence")) or 0.0, 1.0)),
                "recommendedAction": action,
                "notes": [str(note).strip()[:240] for note in notes if str(note).strip()],
                "escalateToOpenAI": bool(item.get("escalateToOpenAI", False)),
                "reason": str(item.get("reason") or "").strip()[:320],
            }
        )
    return reviews
