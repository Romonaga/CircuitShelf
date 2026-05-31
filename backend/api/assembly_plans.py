from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.api.dependencies import ApiDependencies


class AssemblyBuildRequest(BaseModel):
    objective: str = ""
    model: str | None = None
    topK: int = 15
    distanceThreshold: float = 4.0
    maxTokens: int = 1800
    strategy: str = "Vector + CrossEncoder"


class StepUpdateRequest(BaseModel):
    completed: bool = False


class AssistantRequest(BaseModel):
    message: str = ""
    model: str | None = None


class LearningUpdateRequest(BaseModel):
    action: str | None = None
    currentOrdinal: int | None = None


def build_learning_payload(plan: dict, session: dict | None) -> dict:
    steps = plan.get("steps") or []
    current_ordinal = int((session or {}).get("currentOrdinal") or 1)
    current_step = next((step for step in steps if int(step.get("ordinal") or 0) == current_ordinal), None)
    if not current_step and steps:
        current_step = steps[0]
        current_ordinal = int(current_step.get("ordinal") or 1)
    prompt = learning_prompt_for_step(current_step) if current_step else ""
    return {
        "planId": plan.get("id"),
        "currentOrdinal": current_ordinal,
        "modeEnabled": bool((session or {}).get("modeEnabled", True)),
        "stepCount": len(steps),
        "currentStep": current_step,
        "prompt": prompt,
    }


def learning_prompt_for_step(step: dict) -> str:
    step_type = step.get("type")
    title = step.get("title") or "this step"
    if step_type == "wiring":
        return (
            f"Before doing step {step.get('ordinal')}, identify the source pin/rail and destination for {title}. "
            "Say what should be connected, then make the connection and verify continuity before moving on."
        )
    if step_type == "warning":
        return f"Pause on caution step {step.get('ordinal')}. Explain the risk in your own words before continuing."
    return f"Before checking step {step.get('ordinal')}, predict what a correct circuit should show, then perform the test."


def build_assembly_assistant_prompt(plan: dict, message: str) -> str:
    steps = "\n".join(
        f"{step['ordinal']}. [{'done' if step['completed'] else 'open'}] {step['title']}: {step['instruction']} {step.get('note') or ''}"
        for step in plan.get("steps", [])
    )
    sources = "\n".join(
        f"- {source['displayName']} pages {', '.join(str(page) for page in source.get('pages') or [])}"
        for source in plan.get("sources", [])
    )
    notes = "\n".join(f"{note['role']}: {note['message']}" for note in (plan.get("notes") or [])[-8:])
    return (
        "You are CircuitShelf's electronics bench assistant. Use only the assembly plan, checklist, and source notes below. "
        "Give practical next-step guidance, checks to perform, expected readings or behavior when supported, and safety cautions. "
        "If the plan lacks enough evidence, say what is missing.\n\n"
        f"Assembly plan: {plan.get('title')}\n"
        f"Objective: {plan.get('objective')}\n"
        f"Component: {plan.get('componentName')} ({plan.get('componentType')})\n"
        f"Summary: {plan.get('summary')}\n\n"
        f"Checklist:\n{steps}\n\n"
        f"Sources:\n{sources}\n\n"
        f"Recent bench conversation:\n{notes}\n\n"
        f"User says: {message}\n\n"
        "Respond as a concise lab assistant."
    )


def create_router(
    deps: ApiDependencies,
    *,
    assembly_plan_store: Any,
    bench_tools: Any,
    get_rag_response: Callable[..., Any],
    query_ollama_chat_with_retry: Callable[..., Any],
    normalize_sources_for_api: Callable[[Any], Any],
    build_recovery_prompt: Callable[[str, str, Any], str],
    parse_recovered_build_card: Callable[[str, Any], Any],
    recovery_system_prompt: str,
    default_model: str,
    username_for_user: Callable[[Any], str | None],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/assembly-plans")
    async def assembly_plans(req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        return {"plans": assembly_plan_store.list(deps.user_id_for_user(user))}

    @router.get("/api/assembly-plans/{plan_id}")
    async def assembly_plan(plan_id: str, req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        plan = assembly_plan_store.get(plan_id, deps.user_id_for_user(user))
        if not plan:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        return {"plan": plan}

    @router.delete("/api/assembly-plans/{plan_id}")
    async def assembly_plan_delete(plan_id: str, req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        deleted = assembly_plan_store.delete(plan_id, deps.user_id_for_user(user))
        if not deleted:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        return {"ok": True, "deleted": deleted}

    @router.post("/api/assembly-plans/build")
    async def assembly_plan_build(req: Request, payload: AssemblyBuildRequest):
        user, entity, error = deps.require_entity_member(req)
        if error:
            return error
        objective = payload.objective.strip()
        if not objective:
            return JSONResponse({"error": "Build objective is required."}, status_code=400)
        model_name = payload.model or default_model

        _, answer, chat_history, sources, cache_stats, confidence, avg_time, build_card, validation = await run_in_threadpool(
            get_rag_response,
            question=objective,
            chat_history=[],
            show_full_text=False,
            top_k=int(payload.topK),
            dist_thresh=float(payload.distanceThreshold),
            max_tokens=int(payload.maxTokens),
            bypass_cache=True,
            strategy=payload.strategy,
            model_name=model_name,
            user_id=deps.user_id_for_user(user),
            username=username_for_user(user),
            entity_id=entity.entity_id,
            ai_context_type="assembly_plan",
        )
        api_sources = normalize_sources_for_api(sources)
        if not build_card:
            recovery_prompt = build_recovery_prompt(objective, answer, api_sources)
            recovered = await run_in_threadpool(
                query_ollama_chat_with_retry,
                recovery_prompt,
                model_name,
                [],
                system_prompt=recovery_system_prompt,
            )
            build_card = parse_recovered_build_card(recovered, api_sources)
        if not build_card:
            return JSONResponse(
                {
                    "error": "CircuitShelf could not build an assembly plan from the current indexed sources.",
                    "answer": answer,
                    "sources": api_sources,
                    "confidence": confidence,
                    "averageQueryTime": avg_time,
                    "cacheStats": cache_stats,
                    "chatHistory": chat_history,
                    "validation": validation,
                },
                status_code=422,
            )

        plan = assembly_plan_store.create_from_card(
            question=objective,
            card=build_card,
            user_id=deps.user_id_for_user(user),
            created_by=username_for_user(user),
        )
        return {
            "plan": plan,
            "answer": answer,
            "sources": api_sources,
            "confidence": confidence,
            "averageQueryTime": avg_time,
            "cacheStats": cache_stats,
            "chatHistory": chat_history,
            "validation": validation,
        }

    @router.patch("/api/assembly-plans/{plan_id}/steps/{step_id}")
    async def assembly_step_update(plan_id: str, step_id: str, req: Request, payload: StepUpdateRequest):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        updated = assembly_plan_store.set_step_completed(plan_id, step_id, payload.completed, deps.user_id_for_user(user))
        if not updated:
            return JSONResponse({"error": "Assembly step not found."}, status_code=404)
        return {"plan": assembly_plan_store.get(plan_id, deps.user_id_for_user(user))}

    @router.post("/api/assembly-plans/{plan_id}/assistant")
    async def assembly_assistant(plan_id: str, req: Request, payload: AssistantRequest):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        message = payload.message.strip()
        if not message:
            return JSONResponse({"error": "Message is required."}, status_code=400)
        plan = assembly_plan_store.get(plan_id, deps.user_id_for_user(user))
        if not plan:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)

        assembly_plan_store.add_note(plan_id, "user", message, deps.user_id_for_user(user))
        prompt = build_assembly_assistant_prompt(plan, message)
        assistant_answer = await run_in_threadpool(query_ollama_chat_with_retry, prompt, payload.model or default_model, [])
        assembly_plan_store.add_note(plan_id, "assistant", assistant_answer, deps.user_id_for_user(user))
        return {"plan": assembly_plan_store.get(plan_id, deps.user_id_for_user(user)), "answer": assistant_answer}

    @router.get("/api/assembly-plans/{plan_id}/steps/{step_id}/evidence")
    async def assembly_step_evidence(plan_id: str, step_id: str, req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        user_id = deps.user_id_for_user(user)
        if not assembly_plan_store.get(plan_id, user_id):
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        return assembly_plan_store.evidence_for_step(plan_id, step_id, user_id)

    @router.get("/api/assembly-plans/{plan_id}/export")
    async def assembly_plan_export(plan_id: str, req: Request, format: str = Query("markdown")):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        plan = assembly_plan_store.get(plan_id, deps.user_id_for_user(user))
        if not plan:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        return bench_tools.build_assembly_export(plan, format)

    @router.get("/api/assembly-plans/{plan_id}/learning")
    async def assembly_learning_get(plan_id: str, req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        user_id = deps.user_id_for_user(user)
        plan = assembly_plan_store.get(plan_id, user_id)
        if not plan:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        session = assembly_plan_store.get_learning(plan_id, user_id) or assembly_plan_store.start_learning(plan_id, user_id)
        return {"learning": build_learning_payload(plan, session)}

    @router.patch("/api/assembly-plans/{plan_id}/learning")
    async def assembly_learning_update(plan_id: str, req: Request, payload: LearningUpdateRequest):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        user_id = deps.user_id_for_user(user)
        plan = assembly_plan_store.get(plan_id, user_id)
        if not plan:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        session = assembly_plan_store.get_learning(plan_id, user_id) or assembly_plan_store.start_learning(plan_id, user_id)
        current = int((session or {}).get("currentOrdinal") or 1)
        action = str(payload.action or "").lower()
        if action == "next":
            current += 1
        elif action == "previous":
            current -= 1
        elif action == "disable":
            session = assembly_plan_store.update_learning(plan_id, user_id, current_ordinal=current, mode_enabled=False)
            return {"learning": build_learning_payload(plan, session)}
        elif payload.currentOrdinal is not None:
            current = int(payload.currentOrdinal)
        max_ordinal = max((int(step["ordinal"]) for step in plan.get("steps", [])), default=1)
        current = max(1, min(current, max_ordinal))
        session = assembly_plan_store.update_learning(plan_id, user_id, current_ordinal=current, mode_enabled=True)
        return {"learning": build_learning_payload(plan, session)}

    @router.post("/api/assembly-plans/{plan_id}/photo-check")
    async def assembly_photo_check(plan_id: str, req: Request, file: UploadFile = File(...), note: str = Form("")):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        user_id = deps.user_id_for_user(user)
        plan = assembly_plan_store.get(plan_id, user_id)
        if not plan:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        mime_type = file.content_type or "application/octet-stream"
        if not mime_type.startswith("image/"):
            return JSONResponse({"error": "Upload must be an image."}, status_code=400)
        image_bytes = await file.read()
        await file.close()
        if not image_bytes:
            return JSONResponse({"error": "Uploaded image is empty."}, status_code=400)
        if len(image_bytes) > 8 * 1024 * 1024:
            return JSONResponse({"error": "Photo is too large. Use an image under 8 MB."}, status_code=400)
        diagnostics = bench_tools.analyze_bench_photo(image_bytes)
        checklist = bench_tools.build_photo_checklist(plan, note, diagnostics)
        check = assembly_plan_store.add_photo_check(
            plan_id,
            user_id,
            image_mime_type=mime_type,
            image_base64=base64.b64encode(image_bytes).decode("ascii"),
            note=note,
            checklist=checklist,
            diagnostics=diagnostics,
        )
        return {"check": check, "checks": assembly_plan_store.photo_checks(plan_id, user_id)}

    @router.get("/api/assembly-plans/{plan_id}/photo-checks")
    async def assembly_photo_checks(plan_id: str, req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        user_id = deps.user_id_for_user(user)
        if not assembly_plan_store.get(plan_id, user_id):
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        return {"checks": assembly_plan_store.photo_checks(plan_id, user_id)}

    return router
