"""Text normalization for PostgreSQL persistence."""

from __future__ import annotations

from typing import Any


def clean_db_text(value: Any, default: str | None = "") -> str | None:
    """Return text safe for PostgreSQL text fields."""
    if value is None:
        return default
    return str(value).replace("\x00", "")
