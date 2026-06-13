from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.api.dependencies import ApiDependencies
from backend.auth_dependencies import AuthDependencyService
from backend.bootstrap_environment import configure_tesseract
from backend.bootstrap_settings import bootstrap_database_settings
from backend.runtime_container import CircuitShelfRuntime
from backend.services.app_runtime_helpers import TraceLogHelper
from backend.services.project_finder_ai_triage import ProjectFinderAiTriageService
from backend.store_container import StoreContainer, create_store_container
from db.connection import Database, database_url_from_config
from backend.services.settings_runtime import RuntimeSettingsManager
from backend.services.state_manager import StateManager
from backend.services.system_init import SystemInit


USER_PREFERENCE_KEYS = {"ask.retrieval", "ui.theme", "status.sections"}


@dataclass
class BootstrappedRuntime:
    config: Any
    trace_logger: Any
    state: StateManager
    database: Database
    stores: StoreContainer
    runtime_settings: RuntimeSettingsManager
    trace_log_helper: TraceLogHelper
    runtime: CircuitShelfRuntime
    auth_dependencies: AuthDependencyService
    api_dependencies: ApiDependencies


def bootstrap_runtime(*, ingest_status_callback=None, ingest_status_provider=None, lazy_gpu_models: bool = False) -> BootstrappedRuntime:
    config, trace_logger = SystemInit.load_config_and_logger()
    state = StateManager(use_lock=True, cache_capacity=200, trace_logger=trace_logger)
    database = Database(database_url_from_config(config), trace_logger)
    if not database.configured:
        raise RuntimeError(
            "DATABASE_URL is required. CircuitShelf is database-backed and no longer supports file-backed runtime state."
        )

    settings_store, runtime_config_store = bootstrap_database_settings(
        database=database,
        config=config,
        trace_logger=trace_logger,
    )
    stores = create_store_container(database=database, config=config, trace_logger=trace_logger)
    stores.assert_available()
    trace_logger.info("🛠️ Configuration and logger successfully initialized.")

    configure_tesseract(config=config, trace_logger=trace_logger)

    runtime_settings = RuntimeSettingsManager(config, globals(), trace_logger)
    trace_log_file = config.get("TRACE_LOG_FILE", "logs/trace.log")
    trace_log_helper = TraceLogHelper(trace_logger=trace_logger, default_log_file=trace_log_file)

    runtime = CircuitShelfRuntime(
        config=config,
        trace_logger=trace_logger,
        state=state,
        database=database,
        stores=stores,
        runtime_settings=runtime_settings,
        trace_log_helper=trace_log_helper,
        ingest_status_callback=ingest_status_callback,
        ingest_status_provider=ingest_status_provider,
        lazy_gpu_models=lazy_gpu_models,
    )
    stores.project_finder_store.ai_triage_service = ProjectFinderAiTriageService(
        config=config,
        trace_logger=trace_logger,
        ai_provider_store=stores.ai_provider_store,
        openai_assist_service=stores.openai_assist_service,
        query_local_llm=runtime.query_ollama_chat_with_retry,
        local_model_name=runtime.llm_model_name,
    )

    auth_dependencies = AuthDependencyService(
        database=database,
        user_store=stores.user_store,
        entity_store=stores.entity_store,
        session_timeout_seconds=runtime.session_timeout_seconds,
    )

    api_dependencies = ApiDependencies(
        require_authenticated_user=auth_dependencies.require_authenticated_user,
        require_entity_member=auth_dependencies.require_entity_member,
        require_entity_admin=auth_dependencies.require_entity_admin,
        require_system_admin_user=auth_dependencies.require_system_admin_user,
        bearer_token_from_request=auth_dependencies.bearer_token_from_request,
        session_timeout_seconds=runtime.session_timeout_seconds,
        user_payload=auth_dependencies.user_payload,
        user_id_for_user=auth_dependencies.user_id_for_user,
        verify_user=auth_dependencies.verify_user,
        user_store=stores.user_store,
        user_preferences_store=stores.user_preferences_store,
        account_profile_store=stores.account_profile_store,
        entity_store=stores.entity_store,
        password_policy_store=stores.password_policy_store,
        ai_provider_store=stores.ai_provider_store,
        openai_model_service=stores.openai_model_service,
        performance_store=stores.performance_store,
    )

    # Keep these legacy names available to route registration while the backend
    # continues moving toward thinner routers and service-owned behavior.
    boot = BootstrappedRuntime(
        config=config,
        trace_logger=trace_logger,
        state=state,
        database=database,
        stores=stores,
        runtime_settings=runtime_settings,
        trace_log_helper=trace_log_helper,
        runtime=runtime,
        auth_dependencies=auth_dependencies,
        api_dependencies=api_dependencies,
    )
    boot.settings_store = settings_store
    boot.runtime_config_store = runtime_config_store
    return boot
