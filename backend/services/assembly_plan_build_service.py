from __future__ import annotations

from typing import Any, Callable

from fastapi.concurrency import run_in_threadpool


class AssemblyPlanBuildService:
    def __init__(
        self,
        *,
        assembly_plan_store: Any,
        get_rag_response: Callable[..., Any],
        query_ollama_chat_with_retry: Callable[..., Any],
        normalize_sources_for_api: Callable[[Any], Any],
        build_recovery_prompt: Callable[[str, str, Any], str],
        parse_recovered_build_card: Callable[[str, Any], Any],
        recovery_system_prompt: str,
    ):
        self.assembly_plan_store = assembly_plan_store
        self.get_rag_response = get_rag_response
        self.query_ollama_chat_with_retry = query_ollama_chat_with_retry
        self.normalize_sources_for_api = normalize_sources_for_api
        self.build_recovery_prompt = build_recovery_prompt
        self.parse_recovered_build_card = parse_recovered_build_card
        self.recovery_system_prompt = recovery_system_prompt

    async def build(
        self,
        *,
        objective: str,
        model_name: str,
        top_k: int,
        distance_threshold: float,
        max_tokens: int,
        strategy: str,
        user_id: int,
        username: str | None,
        entity_id: int,
    ) -> dict:
        _, answer, chat_history, sources, cache_stats, confidence, avg_time, build_card, validation = await run_in_threadpool(
            self.get_rag_response,
            question=objective,
            chat_history=[],
            show_full_text=False,
            top_k=top_k,
            dist_thresh=distance_threshold,
            max_tokens=max_tokens,
            bypass_cache=True,
            strategy=strategy,
            model_name=model_name,
            user_id=user_id,
            username=username,
            entity_id=entity_id,
            ai_context_type="assembly_plan",
        )
        api_sources = self.normalize_sources_for_api(sources)
        if not build_card:
            recovery_prompt = self.build_recovery_prompt(objective, answer, api_sources)
            recovered = await run_in_threadpool(
                self.query_ollama_chat_with_retry,
                recovery_prompt,
                model_name,
                [],
                system_prompt=self.recovery_system_prompt,
            )
            build_card = self.parse_recovered_build_card(recovered, api_sources)
        if not build_card:
            return {
                "ok": False,
                "answer": answer,
                "sources": api_sources,
                "confidence": confidence,
                "averageQueryTime": avg_time,
                "cacheStats": cache_stats,
                "chatHistory": chat_history,
                "validation": validation,
            }

        plan = self.assembly_plan_store.create_from_card(
            question=objective,
            card=build_card,
            user_id=user_id,
            created_by=username,
        )
        return {
            "ok": True,
            "plan": plan,
            "answer": answer,
            "sources": api_sources,
            "confidence": confidence,
            "averageQueryTime": avg_time,
            "cacheStats": cache_stats,
            "chatHistory": chat_history,
            "validation": validation,
        }
