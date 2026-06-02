# -*- coding: utf-8 -*-

from __future__ import annotations

from contextlib import asynccontextmanager

from backend.app_factory import create_circuitshelf_app, register_api_routes
from backend.bootstrap_runtime import USER_PREFERENCE_KEYS, bootstrap_runtime
from backend.server import mount_react_app, start_app_server
from process_lock import ProcessLockError, acquire_process_lock


boot = bootstrap_runtime(
    ingest_status_provider=lambda: boot.stores.ingest_job_store.get_status() if "boot" in globals() else {},
)

config = boot.config
trace_logger = boot.trace_logger
state = boot.state
database = boot.database
stores = boot.stores
runtime = boot.runtime
auth_dependencies = boot.auth_dependencies
api_dependencies = boot.api_dependencies


def enqueue_index_check(reason="manual", *, requested_by_user_id=None):
    return stores.ingest_job_store.enqueue(
        reason,
        requested_by_user_id=requested_by_user_id,
        details={"requestedFrom": "web"},
    )


@asynccontextmanager
async def lifespan(_app):
    runtime.runtime_status_reporter.start_resource_sampler()
    try:
        yield
    finally:
        runtime.runtime_status_reporter.stop_resource_sampler()


app = create_circuitshelf_app(lifespan=lifespan)

register_api_routes(
    app,
    api_dependencies=api_dependencies,
    user_preference_keys=USER_PREFERENCE_KEYS,
    config=config,
    models=runtime.llm_model_options,
    default_model=runtime.llm_model_name,
    auth_configured=lambda: database.configured and stores.user_store.has_active_users(),
    session_timeout_seconds=runtime.session_timeout_seconds,
    build_readiness_status=runtime.runtime_status_reporter.build_readiness_status,
    build_runtime_status=runtime.runtime_status_reporter.build_runtime_status,
    conversation_store=stores.conversation_store,
    conversation_title_from_question=runtime.conversation_title_from_question,
    lab_inventory_store=stores.lab_inventory_store,
    project_finder_store=stores.project_finder_store,
    parse_inventory_import=runtime.parse_inventory_import,
    require_admin_user=auth_dependencies.require_admin_user,
    settings_store=boot.settings_store,
    runtime_config_store=boot.runtime_config_store,
    runtime_settings=boot.runtime_settings,
    trace_logger=trace_logger,
    start_index_check=enqueue_index_check,
    vector_store=stores.vector_store,
    image_store=stores.image_store,
    refresh_active_state_from_db=runtime.image_state_service.refresh_active_state_from_db,
    reindex_review_source=runtime.incremental_ingest_service.reindex_review_source,
    remove_document_from_store=runtime.document_management_service.remove_document_from_store,
    assembly_plan_store=stores.assembly_plan_store,
    bench_tools=runtime.bench_tools,
    get_rag_response=runtime.rag_service.get_rag_response,
    query_ollama_chat_with_retry=runtime.query_ollama_chat_with_retry,
    normalize_sources_for_api=runtime.normalize_sources_for_api,
    build_recovery_prompt=runtime.build_recovery_prompt,
    parse_recovered_build_card=runtime.parse_recovered_build_card,
    recovery_system_prompt=runtime.recovery_system_prompt,
    username_for_user=auth_dependencies.username_for_user,
    training_dir=runtime.training_dir,
    supported_training_extensions=runtime.supported_training_extensions,
    state=state,
    image_asset_belongs_to_document=runtime.image_asset_belongs_to_document,
    extract_page_number=runtime.document_processing_service.extract_page_number,
    document_source_from_metadata=runtime.document_source_from_metadata,
    source_image_id_from_metadata=runtime.source_image_id_from_metadata,
    extract_pinout_map=runtime.extract_pinout_map,
    get_or_build_datasheet_intelligence=runtime.document_intelligence_service.get_or_build,
    display_source_name=runtime.display_source_name,
    sanitize_for_json=runtime.sanitize_for_json,
    get_last_trace=state.get_last_trace,
    flush_trace_log=boot.trace_log_helper.flush,
    current_trace_log_file=boot.trace_log_helper.current_file,
    tail_text_file=runtime.tail_text_file,
    performance_store=stores.performance_store,
)


if __name__ == "__main__":
    app_host = config.get("APP_HOST", config.get("API_HOST", "127.0.0.1"))
    app_port = config.get("APP_PORT", config.get("API_PORT", 1964))
    server_pid_file = config.get("SERVER_PID_FILE", "data/circuitshelf.pid")

    try:
        with acquire_process_lock(server_pid_file, name="CircuitShelf web"):
            runtime.cleanup_stale_tesseract_temp_files()
            runtime.get_or_build_index()
            mount_react_app(app, react_dist_dir=runtime.react_dist_dir, logger=trace_logger)
            trace_logger.info(f"🌐 CircuitShelf available at http://{app_host}:{app_port}")
            start_app_server(app, host=app_host, port=app_port)
    except ProcessLockError as exc:
        trace_logger.error(str(exc))
        raise SystemExit(1) from exc
