from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from db.ai_provider_store import AIProviderStore


def test_ai_provider_encryption_secret_prefers_secret_file(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    secret_path = tmp_path / "ai.secret"
    secret_path.write_text("file-secret\n", encoding="utf-8")
    config_path.write_text(
        yaml.safe_dump(
            {
                "AI_KEY_ENCRYPTION_SECRET_FILE": str(secret_path),
                "AI_KEY_ENCRYPTION_SECRET": "yaml-secret",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_KEY_ENCRYPTION_SECRET", "env-secret")

    store = AIProviderStore(database=None, config_path=config_path)

    assert store.encryption_secret() == "file-secret"


def test_ai_provider_encryption_secret_allows_environment_fallback_with_warning(monkeypatch, tmp_path: Path):
    class Logger:
        def __init__(self):
            self.messages: list[str] = []

        def warning(self, message: str):
            self.messages.append(message)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"AI_KEY_ENCRYPTION_SECRET_FILE": str(tmp_path / "missing.secret")}), encoding="utf-8")
    monkeypatch.setenv("AI_KEY_ENCRYPTION_SECRET", "env-secret")
    logger = Logger()

    store = AIProviderStore(database=None, config_path=config_path, logger=logger)

    assert store.encryption_secret() == "env-secret"
    assert logger.messages


def test_ai_provider_encryption_secret_allows_legacy_yaml_with_warning(monkeypatch, tmp_path: Path):
    class Logger:
        def __init__(self):
            self.messages: list[str] = []

        def warning(self, message: str):
            self.messages.append(message)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "AI_KEY_ENCRYPTION_SECRET_FILE": str(tmp_path / "missing.secret"),
                "AI_KEY_ENCRYPTION_SECRET": "yaml-secret",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("AI_KEY_ENCRYPTION_SECRET", raising=False)
    logger = Logger()

    store = AIProviderStore(database=None, config_path=config_path, logger=logger)

    assert store.encryption_secret() == "yaml-secret"
    assert logger.messages


def test_ai_provider_encryption_secret_requires_configuration(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"AI_KEY_ENCRYPTION_SECRET_FILE": str(tmp_path / "missing.secret")}), encoding="utf-8")
    monkeypatch.delenv("AI_KEY_ENCRYPTION_SECRET", raising=False)

    store = AIProviderStore(database=None, config_path=config_path)

    with pytest.raises(RuntimeError, match="AI key encryption secret"):
        store.encryption_secret()


def test_ai_provider_settings_row_exposes_admin_key_preview():
    row = {
        "provider_code": "openai",
        "enabled": True,
        "key_preview": "sk-live...1234",
        "admin_key_preview": "sk-admin...5678",
        "provider_project_id": "proj_123",
        "provider_api_key_id": "key_456",
        "key_policy": "system",
        "assist_mode": "auto",
        "default_model": "gpt-5-chat-latest",
        "monthly_budget": 0,
        "warn_percent": 80,
        "stop_percent": 100,
        "updated_at": None,
        "entity_id": None,
        "user_id": None,
    }
    store = AIProviderStore(database=None, config_path="config/config.yaml")
    store.pricing_overrides = lambda **kwargs: []

    settings = store._settings_row(row, scope="system", provider="openai")

    assert settings["hasAdminApiKey"] is True
    assert settings["adminKeyPreview"] == "sk-admin...5678"
    assert settings["providerProjectId"] == "proj_123"
    assert settings["providerApiKeyId"] == "key_456"
    assert "adminApiKey" not in settings


def test_resolved_provider_carries_billing_ids():
    settings = AIProviderStore(database=None, config_path="config/config.yaml")._resolved_provider(
        row={
            "provider": "openai",
            "apiKey": "sk-live",
            "assistMode": "auto",
            "defaultModel": "gpt-5-chat-latest",
            "providerProjectId": "proj_123",
            "providerApiKeyId": "key_456",
            "monthlyBudget": 0,
            "warnPercent": 80,
            "stopPercent": 100,
            "scope": "system",
        },
        paid_by="system",
        owner_user_id=None,
        default_model="fallback",
        entity_id=None,
        user_id=None,
    )

    assert settings["providerProjectId"] == "proj_123"
    assert settings["providerApiKeyId"] == "key_456"


def test_ai_provider_admin_api_key_for_provider_uses_system_secret_row(monkeypatch):
    store = AIProviderStore(database=None, config_path="config/config.yaml")
    monkeypatch.setattr(
        store,
        "_secret_row",
        lambda scope, *, provider, entity_id=None, user_id=None: {"adminApiKey": "admin-secret"} if scope == "system" and provider == "openai" else None,
    )

    assert store.admin_api_key_for_provider("openai") == "admin-secret"
