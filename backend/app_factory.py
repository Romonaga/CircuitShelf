from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from backend.api import account as account_api
from backend.api import ai_settings as ai_settings_api
from backend.api import app_config as app_config_api
from backend.api import assembly_plans as assembly_plans_api
from backend.api import conversations as conversations_api
from backend.api import documents as documents_api
from backend.api import entity as entity_api
from backend.api import inventory as inventory_api
from backend.api import performance as performance_api
from backend.api import query as query_api
from backend.api import review as review_api
from backend.api import settings as settings_api
from backend.api import status as status_api


def create_circuitshelf_app(*, lifespan: Any) -> FastAPI:
    return FastAPI(lifespan=lifespan)


def register_api_routes(
    app: FastAPI,
    *,
    api_dependencies: Any,
    user_preference_keys: set[str],
    config: Any,
    models: list[str],
    default_model: str,
    auth_configured: Any,
    session_timeout_seconds: Any,
    build_readiness_status: Any,
    build_runtime_status: Any,
    conversation_store: Any,
    conversation_title_from_question: Any,
    lab_inventory_store: Any,
    project_finder_store: Any,
    parse_inventory_import: Any,
    require_admin_user: Any,
    settings_store: Any,
    runtime_settings: Any,
    trace_logger: Any,
    start_index_check: Any,
    vector_store: Any,
    image_store: Any,
    refresh_active_state_from_db: Any,
    reindex_review_source: Any,
    remove_document_from_store: Any,
    assembly_plan_store: Any,
    bench_tools: Any,
    get_rag_response: Any,
    query_ollama_chat_with_retry: Any,
    normalize_sources_for_api: Any,
    build_recovery_prompt: Any,
    parse_recovered_build_card: Any,
    recovery_system_prompt: str,
    username_for_user: Any,
    training_dir: str,
    supported_training_extensions: Any,
    state: Any,
    image_asset_belongs_to_document: Any,
    extract_page_number: Any,
    document_source_from_metadata: Any,
    source_image_id_from_metadata: Any,
    extract_pinout_map: Any,
    get_or_build_datasheet_intelligence: Any,
    display_source_name: Any,
    sanitize_for_json: Any,
    get_last_trace: Any,
    flush_trace_log: Any,
    current_trace_log_file: Any,
    tail_text_file: Any,
    performance_store: Any,
) -> None:
    app.include_router(account_api.create_router(api_dependencies, user_preference_keys))
    app.include_router(entity_api.create_router(api_dependencies))
    app.include_router(ai_settings_api.create_router(api_dependencies))
    app.include_router(app_config_api.create_router(
        config=config,
        models=models,
        default_model=default_model,
        auth_configured=auth_configured,
        session_timeout_seconds=session_timeout_seconds,
        build_readiness_status=build_readiness_status,
    ))
    app.include_router(conversations_api.create_router(
        api_dependencies,
        conversation_store=conversation_store,
        conversation_title_from_question=conversation_title_from_question,
    ))
    app.include_router(inventory_api.create_router(
        api_dependencies,
        lab_inventory_store=lab_inventory_store,
        project_finder_store=project_finder_store,
        parse_inventory_import=parse_inventory_import,
    ))
    app.include_router(settings_api.create_router(
        require_admin_user=require_admin_user,
        settings_store=settings_store,
        runtime_settings=runtime_settings,
        trace_logger=trace_logger,
        start_index_check=start_index_check,
    ))
    app.include_router(review_api.create_router(
        deps=api_dependencies,
        vector_store=vector_store,
        image_store=image_store,
        refresh_active_state_from_db=refresh_active_state_from_db,
        reindex_review_source=reindex_review_source,
        remove_document_from_store=remove_document_from_store,
    ))
    app.include_router(assembly_plans_api.create_router(
        api_dependencies,
        assembly_plan_store=assembly_plan_store,
        bench_tools=bench_tools,
        get_rag_response=get_rag_response,
        query_ollama_chat_with_retry=query_ollama_chat_with_retry,
        normalize_sources_for_api=normalize_sources_for_api,
        build_recovery_prompt=build_recovery_prompt,
        parse_recovered_build_card=parse_recovered_build_card,
        recovery_system_prompt=recovery_system_prompt,
        default_model=default_model,
        username_for_user=username_for_user,
    ))
    app.include_router(documents_api.create_router(
        api_dependencies,
        training_dir=training_dir,
        supported_training_extensions=supported_training_extensions,
        vector_store=vector_store,
        image_store=image_store,
        state=state,
        trace_logger=trace_logger,
        start_index_check=start_index_check,
        image_asset_belongs_to_document=image_asset_belongs_to_document,
        extract_page_number=extract_page_number,
        document_source_from_metadata=document_source_from_metadata,
        source_image_id_from_metadata=source_image_id_from_metadata,
        extract_pinout_map=extract_pinout_map,
        get_or_build_datasheet_intelligence=get_or_build_datasheet_intelligence,
        display_source_name=display_source_name,
    ))
    app.include_router(query_api.create_router(
        api_dependencies,
        conversation_store=conversation_store,
        get_rag_response=get_rag_response,
        normalize_sources_for_api=normalize_sources_for_api,
        conversation_title_from_question=conversation_title_from_question,
        username_for_user=username_for_user,
        default_model=default_model,
        trace_logger=trace_logger,
    ))
    app.include_router(status_api.create_router(
        require_admin_user=require_admin_user,
        build_runtime_status=build_runtime_status,
        sanitize_for_json=sanitize_for_json,
        get_last_trace=get_last_trace,
        flush_trace_log=flush_trace_log,
        current_trace_log_file=current_trace_log_file,
        tail_text_file=tail_text_file,
    ))
    app.include_router(performance_api.create_router(
        api_dependencies,
        performance_store=performance_store,
    ))
