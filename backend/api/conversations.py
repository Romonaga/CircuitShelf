from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.api.dependencies import ApiDependencies


class ConversationCreateRequest(BaseModel):
    title: str = "New conversation"


def create_router(
    deps: ApiDependencies,
    *,
    conversation_store: Any,
    conversation_title_from_question: Callable[[str], str] | None = None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/conversations")
    async def conversations_list(req: Request, limit: int = 50):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        return {"conversations": conversation_store.list(deps.user_id_for_user(user), limit=max(1, min(int(limit), 100)))}

    @router.post("/api/conversations")
    async def conversation_create(req: Request, payload: ConversationCreateRequest):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        title = payload.title or "New conversation"
        if conversation_title_from_question:
            title = conversation_title_from_question(title)
        conversation = conversation_store.create(deps.user_id_for_user(user), title)
        return {"conversation": {**conversation, "turns": []}}

    @router.get("/api/conversations/{conversation_id}")
    async def conversation_get(conversation_id: str, req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        conversation = conversation_store.get(conversation_id, deps.user_id_for_user(user))
        if not conversation:
            return JSONResponse({"error": "Conversation not found."}, status_code=404)
        return {"conversation": conversation}

    @router.delete("/api/conversations/{conversation_id}")
    async def conversation_delete(conversation_id: str, req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        removed = conversation_store.archive(conversation_id, deps.user_id_for_user(user))
        if not removed:
            return JSONResponse({"error": "Conversation not found."}, status_code=404)
        return {"ok": True}

    return router
