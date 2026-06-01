from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from db.ai_provider_store import AIProviderStore


def test_ai_provider_encryption_secret_prefers_environment(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"AI_KEY_ENCRYPTION_SECRET": "yaml-secret"}), encoding="utf-8")
    monkeypatch.setenv("AI_KEY_ENCRYPTION_SECRET", "env-secret")

    store = AIProviderStore(database=None, config_path=config_path)

    assert store.encryption_secret() == "env-secret"


def test_ai_provider_encryption_secret_allows_legacy_yaml_with_warning(monkeypatch, tmp_path: Path):
    class Logger:
        def __init__(self):
            self.messages: list[str] = []

        def warning(self, message: str):
            self.messages.append(message)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"AI_KEY_ENCRYPTION_SECRET": "yaml-secret"}), encoding="utf-8")
    monkeypatch.delenv("AI_KEY_ENCRYPTION_SECRET", raising=False)
    logger = Logger()

    store = AIProviderStore(database=None, config_path=config_path, logger=logger)

    assert store.encryption_secret() == "yaml-secret"
    assert logger.messages


def test_ai_provider_encryption_secret_requires_configuration(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({}), encoding="utf-8")
    monkeypatch.delenv("AI_KEY_ENCRYPTION_SECRET", raising=False)

    store = AIProviderStore(database=None, config_path=config_path)

    with pytest.raises(RuntimeError, match="AI_KEY_ENCRYPTION_SECRET"):
        store.encryption_secret()
