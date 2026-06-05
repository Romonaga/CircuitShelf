from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


DEFAULT_AI_KEY_SECRET_FILE = Path("/etc/circuitshelf/ai-key-encryption.secret")


def load_ai_key_encryption_secret(
    *,
    config: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    logger=None,
) -> str:
    loaded_config = dict(config or {})
    if config is None and config_path:
        loaded_config = _load_yaml_config(Path(config_path))

    secret_file = Path(
        str(loaded_config.get("AI_KEY_ENCRYPTION_SECRET_FILE") or DEFAULT_AI_KEY_SECRET_FILE)
    ).expanduser()
    file_secret = _read_secret_file(secret_file)
    if file_secret:
        return file_secret

    env_secret = str(os.environ.get("AI_KEY_ENCRYPTION_SECRET") or "").strip()
    if env_secret:
        _warn(
            logger,
            "AI_KEY_ENCRYPTION_SECRET is being read from the process environment. "
            f"Move it to {secret_file} so the secret is managed as an OS-protected file.",
        )
        return env_secret

    yaml_secret = str(loaded_config.get("AI_KEY_ENCRYPTION_SECRET") or "").strip()
    if yaml_secret:
        _warn(
            logger,
            "AI_KEY_ENCRYPTION_SECRET is being read from config YAML. "
            f"Move it to {secret_file}; do not store encryption material in app config.",
        )
        return yaml_secret

    raise RuntimeError(
        "AI key encryption secret is not configured. Create "
        f"{secret_file} with a long random secret before storing or reading provider keys."
    )


def _read_secret_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def _load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _warn(logger, message: str) -> None:
    if logger:
        logger.warning(message)
