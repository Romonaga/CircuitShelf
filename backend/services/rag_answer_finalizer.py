from __future__ import annotations

from typing import Any, Callable

from backend.services.response_finalizer import finalize_response


class RagAnswerFinalizer:
    def __init__(
        self,
        *,
        openai_assist_service: Any,
        query_llm: Callable,
        system_prompt: str,
        enabled: bool,
        mode: str,
        min_confidence: float,
        max_context_chars: int,
    ):
        self.openai_assist_service = openai_assist_service
        self.query_llm = query_llm
        self.system_prompt = system_prompt
        self.enabled = enabled
        self.mode = mode
        self.min_confidence = min_confidence
        self.max_context_chars = max_context_chars

    def finalize(
        self,
        *,
        question: str,
        answer: str,
        source_payload: list[dict],
        build_card: dict | None,
        model_name: str,
        confidence: Any,
        entity_id: int | None,
        user_id: int | None,
        context_type: str,
        context_id: str | None,
    ):
        openai_finalized = self.openai_assist_service.finalize_response(
            question=question,
            answer=answer,
            source_payload=source_payload,
            build_card=build_card,
            local_model_name=model_name,
            confidence=confidence,
            enabled=self.enabled,
            mode=self.mode,
            min_confidence=self.min_confidence,
            max_context_chars=self.max_context_chars,
            entity_id=entity_id,
            user_id=user_id,
            context_type=context_type,
            context_id=context_id,
        )
        if openai_finalized:
            return openai_finalized

        return finalize_response(
            question=question,
            answer=answer,
            source_payload=source_payload,
            build_card=build_card,
            model_name=model_name,
            confidence=confidence,
            enabled=self.enabled,
            mode=self.mode,
            min_confidence=self.min_confidence,
            max_context_chars=self.max_context_chars,
            llm_call=lambda finalizer_prompt: self.query_llm(
                finalizer_prompt,
                model_name,
                [],
                system_prompt=self.system_prompt,
            ),
        )
