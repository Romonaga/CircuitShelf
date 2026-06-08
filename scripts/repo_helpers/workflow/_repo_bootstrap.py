#!/usr/bin/env python3
"""Helpers for repo-local workstream scripts that run as direct files."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_root_on_path(script_path: str | Path) -> Path:
    """Insert the repo root for direct-file helper execution.

    Repo-local helpers under ``scripts/repo_helpers/workflow`` are often invoked as
    ``python scripts/repo_helpers/workflow/<script>.py`` from the repo root. In that mode
    Python does not automatically add the repo root to ``sys.path`` because the
    script directory becomes the first import location. This helper restores the
    explicit repo root import path without depending on ambient ``PYTHONPATH``.
    """

    repo_root = Path(script_path).resolve().parents[2]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    return repo_root
