# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 06:54:37 2025

@author: sueco, rew
"""


from contextlib import asynccontextmanager

#internal
from backend.app_factory import create_circuitshelf_app, register_api_routes
from backend.api.dependencies import ApiDependencies
from backend.auth_dependencies import AuthDependencyService
from backend.bootstrap_environment import configure_nltk_and_tesseract
from backend.bootstrap_settings import bootstrap_database_settings
from backend.runtime_container import CircuitShelfRuntime
from backend.server import mount_react_app, start_app_server
from backend.store_container import create_store_container
from backend.services.app_runtime_helpers import TraceLogHelper
from state_manager import StateManager
from system_init import SystemInit
from db.connection import Database, database_url_from_config
from process_lock import ProcessLockError, acquire_process_lock
from settings_runtime import RuntimeSettingsManager

#Inits the logger as well as the configuraqtion system
config, trace_logger = SystemInit.load_config_and_logger()
state = StateManager(use_lock=True, cache_capacity=200, trace_logger=trace_logger)
database = Database(database_url_from_config(config), trace_logger)
if not database.configured:
    raise RuntimeError("DATABASE_URL is required. CircuitShelf is database-backed and no longer supports file-backed runtime state.")

settings_store, runtime_config_store = bootstrap_database_settings(
    database=database,
    config=config,
    trace_logger=trace_logger,
)
stores = create_store_container(database=database, config=config, trace_logger=trace_logger)
stores.assert_available()
user_store = stores.user_store
entity_store = stores.entity_store
password_policy_store = stores.password_policy_store
account_profile_store = stores.account_profile_store
ai_provider_store = stores.ai_provider_store
openai_assist_service = stores.openai_assist_service
openai_model_service = stores.openai_model_service
user_preferences_store = stores.user_preferences_store
query_log_store = stores.query_log_store
performance_store = stores.performance_store
conversation_store = stores.conversation_store
vector_store = stores.vector_store
image_store = stores.image_store
intelligence_store = stores.intelligence_store
assembly_plan_store = stores.assembly_plan_store
lab_inventory_store = stores.lab_inventory_store
project_finder_store = stores.project_finder_store
db_response_cache = stores.db_response_cache
trace_logger.info("🛠️ Configuration and logger successfully initialized.")

configure_nltk_and_tesseract(config=config, trace_logger=trace_logger)


runtime_settings = RuntimeSettingsManager(config, globals(), trace_logger)
TRACE_LOG_FILE = config.get("TRACE_LOG_FILE", "logs/trace.log")
trace_log_helper = TraceLogHelper(trace_logger=trace_logger, default_log_file=TRACE_LOG_FILE)


runtime = CircuitShelfRuntime(
    config=config,
    trace_logger=trace_logger,
    state=state,
    database=database,
    stores=stores,
    runtime_settings=runtime_settings,
    trace_log_helper=trace_log_helper,
)

REACT_DIST_DIR = runtime.react_dist_dir
TRAINING_DIR = runtime.training_dir
LLM_MODEL_NAME = runtime.llm_model_name
LLM_MODEL_OPTIONS = runtime.llm_model_options
runtime_status_reporter = runtime.runtime_status_reporter
start_index_check = runtime.index_lifecycle_service.start_index_check
refresh_active_state_from_db = runtime.image_state_service.refresh_active_state_from_db
reindex_review_source = runtime.incremental_ingest_service.reindex_review_source
document_management_service = runtime.document_management_service
rag_service = runtime.rag_service
query_ollama_chat_with_retry = runtime.query_ollama_chat_with_retry
supported_training_extensions = runtime.supported_training_extensions
extract_page_number = runtime.document_processing_service.extract_page_number
document_intelligence_service = runtime.document_intelligence_service
session_timeout_seconds = runtime.session_timeout_seconds
start_ingest_watcher = runtime.start_ingest_watcher
stop_ingest_watcher = runtime.stop_ingest_watcher
cleanup_stale_tesseract_temp_files = runtime.cleanup_stale_tesseract_temp_files
get_or_build_index = runtime.get_or_build_index
conversation_title_from_question = runtime.conversation_title_from_question
parse_inventory_import = runtime.parse_inventory_import
bench_tools = runtime.bench_tools
normalize_sources_for_api = runtime.normalize_sources_for_api
build_recovery_prompt = runtime.build_recovery_prompt
parse_recovered_build_card = runtime.parse_recovered_build_card
RECOVERY_SYSTEM_PROMPT = runtime.recovery_system_prompt
image_asset_belongs_to_document = runtime.image_asset_belongs_to_document
document_source_from_metadata = runtime.document_source_from_metadata
source_image_id_from_metadata = runtime.source_image_id_from_metadata
extract_pinout_map = runtime.extract_pinout_map
display_source_name = runtime.display_source_name
sanitize_for_json = runtime.sanitize_for_json
tail_text_file = runtime.tail_text_file


@asynccontextmanager
async def lifespan(_app):
    start_ingest_watcher()
    try:
        yield
    finally:
        stop_ingest_watcher()


app = create_circuitshelf_app(lifespan=lifespan)


USER_PREFERENCE_KEYS = {"ask.retrieval", "ui.theme"}


auth_dependencies = AuthDependencyService(
    database=database,
    user_store=user_store,
    entity_store=entity_store,
    session_timeout_seconds=session_timeout_seconds,
)

api_dependencies = ApiDependencies(
    require_authenticated_user=auth_dependencies.require_authenticated_user,
    require_entity_member=auth_dependencies.require_entity_member,
    require_entity_admin=auth_dependencies.require_entity_admin,
    require_system_admin_user=auth_dependencies.require_system_admin_user,
    bearer_token_from_request=auth_dependencies.bearer_token_from_request,
    session_timeout_seconds=session_timeout_seconds,
    user_payload=auth_dependencies.user_payload,
    user_id_for_user=auth_dependencies.user_id_for_user,
    verify_user=auth_dependencies.verify_user,
    user_store=user_store,
    user_preferences_store=user_preferences_store,
    account_profile_store=account_profile_store,
    entity_store=entity_store,
    password_policy_store=password_policy_store,
    ai_provider_store=ai_provider_store,
    openai_model_service=openai_model_service,
    performance_store=performance_store,
)

register_api_routes(
    app,
    api_dependencies=api_dependencies,
    user_preference_keys=USER_PREFERENCE_KEYS,
    config=config,
    models=LLM_MODEL_OPTIONS,
    default_model=LLM_MODEL_NAME,
    auth_configured=lambda: database.configured and user_store.has_active_users(),
    session_timeout_seconds=session_timeout_seconds,
    build_readiness_status=runtime_status_reporter.build_readiness_status,
    build_runtime_status=runtime_status_reporter.build_runtime_status,
    conversation_store=conversation_store,
    conversation_title_from_question=conversation_title_from_question,
    lab_inventory_store=lab_inventory_store,
    project_finder_store=project_finder_store,
    parse_inventory_import=parse_inventory_import,
    require_admin_user=auth_dependencies.require_admin_user,
    settings_store=settings_store,
    runtime_config_store=runtime_config_store,
    runtime_settings=runtime_settings,
    trace_logger=trace_logger,
    start_index_check=start_index_check,
    vector_store=vector_store,
    image_store=image_store,
    refresh_active_state_from_db=refresh_active_state_from_db,
    reindex_review_source=reindex_review_source,
    remove_document_from_store=document_management_service.remove_document_from_store,
    assembly_plan_store=assembly_plan_store,
    bench_tools=bench_tools,
    get_rag_response=rag_service.get_rag_response,
    query_ollama_chat_with_retry=query_ollama_chat_with_retry,
    normalize_sources_for_api=normalize_sources_for_api,
    build_recovery_prompt=build_recovery_prompt,
    parse_recovered_build_card=parse_recovered_build_card,
    recovery_system_prompt=RECOVERY_SYSTEM_PROMPT,
    username_for_user=auth_dependencies.username_for_user,
    training_dir=TRAINING_DIR,
    supported_training_extensions=supported_training_extensions,
    state=state,
    image_asset_belongs_to_document=image_asset_belongs_to_document,
    extract_page_number=extract_page_number,
    document_source_from_metadata=document_source_from_metadata,
    source_image_id_from_metadata=source_image_id_from_metadata,
    extract_pinout_map=extract_pinout_map,
    get_or_build_datasheet_intelligence=document_intelligence_service.get_or_build,
    display_source_name=display_source_name,
    sanitize_for_json=sanitize_for_json,
    get_last_trace=state.get_last_trace,
    flush_trace_log=trace_log_helper.flush,
    current_trace_log_file=trace_log_helper.current_file,
    tail_text_file=tail_text_file,
    performance_store=performance_store,
)


if __name__ == "__main__":

    app_host = config.get("APP_HOST", config.get("API_HOST", "127.0.0.1"))
    app_port = config.get("APP_PORT", config.get("API_PORT", 1964))
    server_pid_file = config.get("SERVER_PID_FILE", "data/circuitshelf.pid")

    try:
        with acquire_process_lock(server_pid_file, name="CircuitShelf"):
            cleanup_stale_tesseract_temp_files()
            get_or_build_index()

            mount_react_app(app, react_dist_dir=REACT_DIST_DIR, logger=trace_logger)
            trace_logger.info(f"🌐 CircuitShelf available at http://{app_host}:{app_port}")
            start_app_server(app, host=app_host, port=app_port)
    except ProcessLockError as exc:
        trace_logger.error(str(exc))
        raise SystemExit(1) from exc
