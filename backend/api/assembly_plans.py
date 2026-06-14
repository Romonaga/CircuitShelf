from __future__ import annotations

import base64
import time
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from backend.api.dependencies import ApiDependencies
from backend.services.assembly_assistant_service import answer_assembly_assistant
from backend.services.assembly_learning_service import build_learning_payload, update_learning_session
from backend.services.assembly_plan_build_service import AssemblyPlanBuildService
from backend.services.circuit_graph import build_circuit_graph
from backend.services.circuit_graph_ai import CircuitGraphAiEnrichmentService
from backend.services.conversation_bench_plan_service import ConversationBenchPlanService
from backend.services.ingestion_ai_review_service import estimate_local_tokens
from backend.services.kicad_export import build_kicad_project_package
from backend.services.openai_assist_utils import parse_json_object


class AssemblyBuildRequest(BaseModel):
    objective: str = ""
    model: str | None = None
    topK: int = 15
    distanceThreshold: float = 4.0
    maxTokens: int = 1800
    strategy: str = "Vector + CrossEncoder"


class ConversationBenchPlanRequest(BaseModel):
    conversationId: str = ""
    objective: str = ""


class StepUpdateRequest(BaseModel):
    completed: bool = False


class AssistantRequest(BaseModel):
    message: str = ""
    model: str | None = None


class LearningUpdateRequest(BaseModel):
    action: str | None = None
    currentOrdinal: int | None = None


def create_router(
    deps: ApiDependencies,
    *,
    assembly_plan_store: Any,
    conversation_store: Any,
    bench_tools: Any,
    openai_assist_service: Any | None,
    get_rag_response: Callable[..., Any],
    query_ollama_chat_with_retry: Callable[..., Any],
    normalize_sources_for_api: Callable[[Any], Any],
    build_recovery_prompt: Callable[[str, str, Any], str],
    parse_recovered_build_card: Callable[[str, Any], Any],
    recovery_system_prompt: str,
    default_model: str,
    username_for_user: Callable[[Any], str | None],
    trace_logger: Any = None,
) -> APIRouter:
    router = APIRouter()
    build_service = AssemblyPlanBuildService(
        assembly_plan_store=assembly_plan_store,
        get_rag_response=get_rag_response,
        query_ollama_chat_with_retry=query_ollama_chat_with_retry,
        normalize_sources_for_api=normalize_sources_for_api,
        build_recovery_prompt=build_recovery_prompt,
        parse_recovered_build_card=parse_recovered_build_card,
        recovery_system_prompt=recovery_system_prompt,
    )
    graph_ai_service = CircuitGraphAiEnrichmentService(
        ai_provider_store=deps.ai_provider_store,
        openai_assist_service=openai_assist_service,
        query_local_llm=query_ollama_chat_with_retry,
        local_model_name=default_model,
        trace_logger=trace_logger,
    )
    conversation_bench_service = ConversationBenchPlanService(
        conversation_store=conversation_store,
        assembly_plan_store=assembly_plan_store,
        ai_provider_store=deps.ai_provider_store,
        openai_assist_service=openai_assist_service,
        query_local_llm=query_ollama_chat_with_retry,
        local_model_name=default_model,
        trace_logger=trace_logger,
    )

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

        result = await build_service.build(
            objective=objective,
            model_name=model_name,
            top_k=int(payload.topK),
            distance_threshold=float(payload.distanceThreshold),
            max_tokens=int(payload.maxTokens),
            strategy=payload.strategy,
            user_id=deps.user_id_for_user(user),
            username=username_for_user(user),
            entity_id=entity.entity_id,
        )
        if not result.get("ok"):
            return JSONResponse(
                {
                    "error": "CircuitShelf could not build an assembly plan from the current indexed sources.",
                    "answer": result.get("answer"),
                    "sources": result.get("sources"),
                    "confidence": result.get("confidence"),
                    "averageQueryTime": result.get("averageQueryTime"),
                    "cacheStats": result.get("cacheStats"),
                    "chatHistory": result.get("chatHistory"),
                    "validation": result.get("validation"),
                },
                status_code=422,
            )
        return {
            "plan": result.get("plan"),
            "answer": result.get("answer"),
            "sources": result.get("sources"),
            "confidence": result.get("confidence"),
            "averageQueryTime": result.get("averageQueryTime"),
            "cacheStats": result.get("cacheStats"),
            "chatHistory": result.get("chatHistory"),
            "validation": result.get("validation"),
        }

    @router.post("/api/assembly-plans/from-conversation")
    async def assembly_plan_from_conversation(req: Request, payload: ConversationBenchPlanRequest):
        user, entity, error = deps.require_entity_member(req)
        if error:
            return error
        conversation_id = payload.conversationId.strip()
        if not conversation_id:
            return JSONResponse({"error": "Conversation id is required."}, status_code=400)
        user_id = deps.user_id_for_user(user)
        result = await run_in_threadpool(
            conversation_bench_service.create_plan,
            conversation_id=conversation_id,
            user_id=user_id,
            username=username_for_user(user),
            entity_id=entity.entity_id,
            objective_override=payload.objective,
        )
        if not result.get("ok"):
            return JSONResponse(
                {
                    "error": result.get("error") or "Conversation could not be converted into a Bench plan.",
                    "aiReview": result.get("aiReview"),
                    "validation": result.get("validation"),
                },
                status_code=int(result.get("status") or 422),
            )
        return {
            "plan": result.get("plan"),
            "source": result.get("source"),
            "aiReview": result.get("aiReview"),
            "validation": result.get("validation"),
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

        return await answer_assembly_assistant(
            assembly_plan_store=assembly_plan_store,
            query_ollama_chat_with_retry=query_ollama_chat_with_retry,
            plan_id=plan_id,
            user_id=deps.user_id_for_user(user),
            plan=plan,
            message=message,
            model_name=payload.model or default_model,
        )

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

    @router.get("/api/assembly-plans/{plan_id}/circuit-graph")
    async def assembly_plan_circuit_graph(plan_id: str, req: Request, enrich: bool = Query(False)):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        user_id = deps.user_id_for_user(user)
        plan = assembly_plan_store.get(plan_id, user_id)
        if not plan:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        graph = build_circuit_graph(plan)
        if not enrich:
            return {"graph": graph}
        ai_enrichment = await run_in_threadpool(
            graph_ai_service.enrich,
            plan=plan,
            graph=graph,
            entity_id=current_entity_id(deps, user_id),
            user_id=user_id,
        )
        graph["aiEnrichment"] = ai_enrichment
        return {"graph": graph}

    @router.get("/api/assembly-plans/{plan_id}/kicad-project")
    async def assembly_plan_kicad_project(plan_id: str, req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        plan = assembly_plan_store.get(plan_id, deps.user_id_for_user(user))
        if not plan:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        graph = build_circuit_graph(plan)
        package = build_kicad_project_package(plan, graph)
        if not package.get("exportable"):
            return JSONResponse(
                {
                    "error": "Circuit graph is not ready for KiCad export.",
                    "package": package,
                },
                status_code=422,
            )
        return {"package": package}

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
        return {"learning": update_learning_session(assembly_plan_store, plan_id, user_id, plan, payload)}

    @router.post("/api/assembly-plans/{plan_id}/photo-check")
    async def assembly_photo_check(
        plan_id: str,
        req: Request,
        file: UploadFile = File(...),
        note: str = Form(""),
        stepId: str = Form(""),
    ):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        user_id = deps.user_id_for_user(user)
        plan = assembly_plan_store.get(plan_id, user_id)
        if not plan:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        step_id = stepId.strip() or None
        step = bench_tools.step_for_id(plan, step_id)
        if step_id and not step:
            return JSONResponse({"error": "Assembly step not found."}, status_code=404)
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
        verification = None
        local_review = None
        if step:
            local_review = await run_in_threadpool(
                run_local_step_photo_review,
                bench_tools=bench_tools,
                query_ollama_chat_with_retry=query_ollama_chat_with_retry,
                model_name=default_model,
                plan=plan,
                step=step,
                note=note,
                diagnostics=diagnostics,
            )
            record_local_photo_review_event(
                deps.ai_provider_store,
                local_review,
                entity_id=current_entity_id(deps, user_id),
                user_id=user_id,
                model_name=default_model,
            )
            verification = bench_tools.deterministic_step_photo_verification(
                step=step,
                diagnostics=diagnostics,
                note=note,
                local_review=local_review,
            )
            if should_escalate_step_photo_to_openai(verification, local_review, diagnostics):
                openai_review = await run_in_threadpool(
                    verify_bench_photo_with_openai,
                    openai_assist_service=openai_assist_service,
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    plan=plan,
                    step=step,
                    note=note,
                    diagnostics=diagnostics,
                    local_review=local_review,
                    entity_id=current_entity_id(deps, user_id),
                    user_id=user_id,
                )
                if openai_review:
                    verification = bench_tools.deterministic_step_photo_verification(
                        step=step,
                        diagnostics=diagnostics,
                        note=note,
                        openai_review=openai_review,
                    )
            checklist = bench_tools.build_step_photo_checklist(
                plan=plan,
                step=step,
                note=note,
                diagnostics=diagnostics,
                verification=verification,
            )
        else:
            verification = bench_tools.deterministic_step_photo_verification(
                step=None,
                diagnostics=diagnostics,
                note=note,
            )
            checklist = bench_tools.build_photo_checklist(plan, note, diagnostics)
        check = assembly_plan_store.add_photo_check(
            plan_id,
            user_id,
            step_id=step_id,
            image_mime_type=mime_type,
            image_base64=base64.b64encode(image_bytes).decode("ascii"),
            note=note,
            checklist=checklist,
            diagnostics=diagnostics,
            verification=verification,
        )
        return {"check": check, "checks": assembly_plan_store.photo_checks(plan_id, user_id, step_id=step_id)}

    @router.get("/api/assembly-plans/{plan_id}/photo-checks")
    async def assembly_photo_checks(plan_id: str, req: Request, stepId: str = Query("")):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        user_id = deps.user_id_for_user(user)
        plan = assembly_plan_store.get(plan_id, user_id)
        if not plan:
            return JSONResponse({"error": "Assembly plan not found."}, status_code=404)
        step_id = stepId.strip() or None
        if step_id and not bench_tools.step_for_id(plan, step_id):
            return JSONResponse({"error": "Assembly step not found."}, status_code=404)
        return {"checks": assembly_plan_store.photo_checks(plan_id, user_id, step_id=step_id)}

    return router


def run_local_step_photo_review(
    *,
    bench_tools: Any,
    query_ollama_chat_with_retry: Callable[..., Any],
    model_name: str,
    plan: dict[str, Any],
    step: dict[str, Any],
    note: str,
    diagnostics: dict[str, Any],
) -> dict[str, Any] | None:
    if not query_ollama_chat_with_retry or not model_name:
        return None
    system_prompt = bench_tools.LOCAL_STEP_PHOTO_REVIEW_SYSTEM_PROMPT
    prompt = bench_tools.build_step_photo_local_prompt(
        plan=plan,
        step=step,
        note=note,
        diagnostics=diagnostics,
    )
    started_at = time.time()
    try:
        raw = query_ollama_chat_with_retry(
            prompt,
            model_name,
            chat_history=[],
            system_prompt=system_prompt,
            gpu_priority=85,
            gpu_owner="bench-photo-verification",
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
        return {
            "status": "cannot_verify",
            "confidence": 0.0,
            "summary": "Local bench photo review failed.",
            "findings": ["Local AI could not review the step photo diagnostics."],
            "requestedEvidence": ["Use manual inspection or retry with a clearer photo."],
            "escalateToOpenAI": False,
            "reason": "local bench photo review failed",
            "raw": "",
            "_inputTokenEstimate": 0,
            "_outputTokenEstimate": 0,
            "_latencyMs": int((time.time() - started_at) * 1000),
            "_success": False,
            "_errorMessage": str(exc)[:240],
        }


def record_local_photo_review_event(
    ai_provider_store: Any,
    result: dict[str, Any] | None,
    *,
    entity_id: int | None,
    user_id: int | None,
    model_name: str,
) -> None:
    if not result or not ai_provider_store or not hasattr(ai_provider_store, "record_ai_assist_event"):
        return
    ai_provider_store.record_ai_assist_event(
        entity_id=entity_id,
        user_id=user_id,
        provider="ollama",
        task_type="photo_check",
        model_name=model_name or "local",
        context_type="bench_photo_verification",
        input_tokens=int(result.get("_inputTokenEstimate") or 0),
        output_tokens=int(result.get("_outputTokenEstimate") or 0),
        estimated_cost=0.0,
        paid_by="entity" if entity_id is not None else "user",
        success=bool(result.get("_success", True)),
        error_message=result.get("_errorMessage"),
        decision_reason="Local bench photo verification triaged image diagnostics before any OpenAI vision escalation.",
        latency_ms=int(result.get("_latencyMs") or 0),
    )


def should_escalate_step_photo_to_openai(
    verification: dict[str, Any],
    local_review: dict[str, Any] | None,
    diagnostics: dict[str, Any],
) -> bool:
    if local_review and bool(local_review.get("escalateToOpenAI")):
        return True
    if diagnostics.get("warnings"):
        return False
    confidence = verification.get("confidence")
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    return verification.get("status") == "cannot_verify" and confidence_value < 0.55


def verify_bench_photo_with_openai(
    *,
    openai_assist_service: Any | None,
    image_bytes: bytes,
    mime_type: str,
    plan: dict[str, Any],
    step: dict[str, Any],
    note: str,
    diagnostics: dict[str, Any],
    local_review: dict[str, Any] | None,
    entity_id: int | None,
    user_id: int | None,
) -> dict[str, Any] | None:
    if not openai_assist_service or not hasattr(openai_assist_service, "verify_bench_photo"):
        return None
    return openai_assist_service.verify_bench_photo(
        image_bytes=image_bytes,
        mime_type=mime_type,
        plan=plan,
        step=step,
        note=note,
        diagnostics=diagnostics,
        local_review=local_review,
        entity_id=entity_id,
        user_id=user_id,
        enabled=True,
        decision_reason="Local bench photo verification requested OpenAI vision escalation.",
    )


def current_entity_id(deps: ApiDependencies, user_id: int | None) -> int | None:
    if user_id is None or not getattr(deps, "entity_store", None):
        return None
    entity = deps.entity_store.current_for_user(user_id)
    return getattr(entity, "entity_id", None)
