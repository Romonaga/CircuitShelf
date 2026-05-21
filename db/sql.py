from __future__ import annotations

from functools import lru_cache
from pathlib import Path


QUERY_DIR = Path(__file__).resolve().parent / "queries"


@lru_cache(maxsize=128)
def load_query(name: str) -> str:
    path = QUERY_DIR / name
    if path.suffix != ".sql":
        raise ValueError(f"SQL query files must use .sql extension: {name}")
    if not path.is_file():
        raise FileNotFoundError(f"SQL query file not found: {path}")
    return path.read_text(encoding="utf-8")
