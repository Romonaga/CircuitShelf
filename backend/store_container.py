from dataclasses import dataclass

from backend.services.openai_assist_service import OpenAIAssistService
from backend.services.openai_model_service import OpenAIModelService
from db.account_profile import AccountProfileStore
from db.ai_provider_store import AIProviderStore
from db.assembly_plan_store import AssemblyPlanStore
from db.conversation_store import ConversationStore
from db.datasheet_intelligence_store import DatasheetIntelligenceStore
from db.entities import EntityStore
from db.image_store import ImageStore
from db.lab_inventory import LabInventoryStore, ProjectFinderStore
from db.performance_store import PerformanceStore
from db.query_log_store import QueryLogStore
from db.response_cache_store import PostgresResponseCache
from db.security_policy import PasswordPolicyStore
from db.user_preferences import UserPreferencesStore
from db.users import UserStore
from db.vector_store import VectorStore


@dataclass
class StoreContainer:
    user_store: UserStore
    entity_store: EntityStore
    password_policy_store: PasswordPolicyStore
    account_profile_store: AccountProfileStore
    ai_provider_store: AIProviderStore
    openai_assist_service: OpenAIAssistService
    openai_model_service: OpenAIModelService
    user_preferences_store: UserPreferencesStore
    query_log_store: QueryLogStore
    performance_store: PerformanceStore
    conversation_store: ConversationStore
    vector_store: VectorStore
    image_store: ImageStore
    intelligence_store: DatasheetIntelligenceStore
    assembly_plan_store: AssemblyPlanStore
    lab_inventory_store: LabInventoryStore
    project_finder_store: ProjectFinderStore
    db_response_cache: PostgresResponseCache

    def assert_available(self) -> None:
        checks = [
            (self.vector_store, "Postgres vector store"),
            (self.image_store, "Postgres image store"),
            (self.intelligence_store, "Postgres datasheet intelligence store"),
            (self.db_response_cache, "Postgres response cache"),
            (self.query_log_store, "Postgres query log"),
            (self.conversation_store, "Postgres conversation store"),
            (self.assembly_plan_store, "Postgres assembly plan store"),
            (self.user_preferences_store, "Postgres user preferences store"),
            (self.lab_inventory_store, "Postgres lab inventory store"),
        ]
        for store, label in checks:
            if not store.available():
                raise RuntimeError(f"{label} is unavailable. Run database migrations before starting CircuitShelf.")


def create_store_container(*, database, config, trace_logger) -> StoreContainer:
    training_dir = config.get("TRAINING_DIR", "training")
    lab_inventory_store = LabInventoryStore(database, trace_logger)
    ai_provider_store = AIProviderStore(database, "config/config.yaml", trace_logger)
    return StoreContainer(
        user_store=UserStore(database, trace_logger),
        entity_store=EntityStore(database, trace_logger),
        password_policy_store=PasswordPolicyStore(database, trace_logger),
        account_profile_store=AccountProfileStore(database, trace_logger),
        ai_provider_store=ai_provider_store,
        openai_assist_service=OpenAIAssistService(ai_provider_store, trace_logger),
        openai_model_service=OpenAIModelService(ai_provider_store, trace_logger),
        user_preferences_store=UserPreferencesStore(database, trace_logger),
        query_log_store=QueryLogStore(database, trace_logger),
        performance_store=PerformanceStore(database, trace_logger, sample_interval_seconds=5),
        conversation_store=ConversationStore(database, trace_logger),
        vector_store=VectorStore(database, training_dir, config.get("EMBED_MODEL_NAME"), trace_logger),
        image_store=ImageStore(database, training_dir, trace_logger),
        intelligence_store=DatasheetIntelligenceStore(database, trace_logger),
        assembly_plan_store=AssemblyPlanStore(database, training_dir, trace_logger),
        lab_inventory_store=lab_inventory_store,
        project_finder_store=ProjectFinderStore(database, lab_inventory_store, trace_logger),
        db_response_cache=PostgresResponseCache(
            database,
            capacity=config.get("RESPONSE_CACHE_CAPACITY", 200),
            logger=trace_logger,
        ),
    )
