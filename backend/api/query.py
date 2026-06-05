from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.api.dependencies import ApiDependencies


class QueryRequest(BaseModel):
    question: str = ""
    conversationId: str | None = None
    chatHistory: list = Field(default_factory=list)
    showFullText: bool = False
    topK: int = 15
    distanceThreshold: float = 4.0
    maxTokens: int = 1800
    bypassCache: bool = True
    strategy: str = "Vector + CrossEncoder"
    model: str | None = None


def create_router(
    deps: ApiDependencies,
    *,
    conversation_store: Any,
    get_rag_response: Callable[..., Any],
    normalize_sources_for_api: Callable[[Any], Any],
    conversation_title_from_question: Callable[[str], str],
    username_for_user: Callable[[Any], str | None],
    default_model: str,
    trace_logger: Any,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/query")
    async def react_query(req: Request, payload: QueryRequest):
        try:
            user, entity, error = deps.require_entity_member(req)
            if error:
                return error
            question = payload.question
            if not question.strip():
                return {"error": "No question provided."}
            username = username_for_user(user)
            user_id = deps.user_id_for_user(user)
            conversation_id = payload.conversationId
            if conversation_id:
                conversation = conversation_store.get(str(conversation_id), user_id)
                if not conversation:
                    return JSONResponse({"error": "Conversation not found."}, status_code=404)
            else:
                conversation = conversation_store.create(user_id, conversation_title_from_question(question))
                conversation_id = conversation["id"]

            model_name = payload.model or default_model
            _, answer, chat_history, sources, cache_stats, confidence, avg_time, build_card, validation = await run_in_threadpool(
                get_rag_response,
                question=question,
                chat_history=payload.chatHistory,
                show_full_text=payload.showFullText,
                top_k=int(payload.topK),
                dist_thresh=float(payload.distanceThreshold),
                max_tokens=int(payload.maxTokens),
                bypass_cache=payload.bypassCache,
                strategy=payload.strategy,
                model_name=model_name,
                user_id=user_id,
                username=username,
                entity_id=entity.entity_id,
                ai_context_type="conversation",
                ai_context_id=str(conversation_id),
            )
            stored_answer = chat_history[-1][1] if chat_history else answer
            api_sources = normalize_sources_for_api(sources)
            response_snapshot = {
                "question": question,
                "answer": answer,
                "chatHistory": chat_history,
                "sources": api_sources,
                "cacheStats": cache_stats,
                "confidence": confidence,
                "averageQueryTime": avg_time,
                "buildCard": build_card,
                "validation": validation,
            }
            conversation_store.append_turn(
                conversation_id=str(conversation_id),
                question=question,
                answer=stored_answer,
                model_name=model_name,
                retrieval_strategy=payload.strategy,
                confidence_score=confidence,
                response_snapshot=response_snapshot,
            )
            conversation = conversation_store.get(str(conversation_id), user_id)

            return {
                "conversation": conversation,
                "question": question,
                "answer": answer,
                "chatHistory": chat_history,
                "sources": api_sources,
                "cacheStats": cache_stats,
                "confidence": confidence,
                "averageQueryTime": avg_time,
                "buildCard": build_card,
                "validation": validation,
            }
        except Exception as exc:
            trace_logger.error(f"❌ [API] React query failed: {exc}")
            return {"error": str(exc)}

    return router
