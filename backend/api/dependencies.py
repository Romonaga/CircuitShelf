from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ApiDependencies:
    require_authenticated_user: Callable[[Any], tuple[Any, Any]]
    require_entity_member: Callable[[Any], tuple[Any, Any, Any]]
    require_entity_admin: Callable[[Any], tuple[Any, Any, Any]]
    require_system_admin_user: Callable[[Any], tuple[Any, Any]]
    bearer_token_from_request: Callable[[Any], str]
    session_timeout_seconds: Callable[[], int]
    user_payload: Callable[[Any], dict]
    user_id_for_user: Callable[[Any], int | None]
    verify_user: Callable[[str, str], Any]
    user_store: Any
    user_preferences_store: Any
    account_profile_store: Any
    entity_store: Any
    password_policy_store: Any
    ai_provider_store: Any
    performance_store: Any | None = None
