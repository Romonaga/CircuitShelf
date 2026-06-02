#!/usr/bin/env python3
"""Small helper to keep workflow docs ASCII-safe."""

from __future__ import annotations


def ensure_ascii(label: str, content: str) -> None:
    try:
        content.encode("ascii")
    except UnicodeEncodeError as exc:  # pragma: no cover
        raise ValueError(f"{label} contains non-ASCII text at position {exc.start}") from exc
