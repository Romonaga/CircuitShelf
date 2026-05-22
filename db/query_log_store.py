from __future__ import annotations

import os
from typing import Any

from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query


class QueryLogStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("query_log_available.sql"))
            return True
        except UndefinedTable:
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"DB query log is not available: {exc}")
            return False

    def log_query(
        self,
        *,
        model_name: str,
        retrieval_strategy: str,
        question: str,
        retrieval_query: str,
        elapsed_ms: int,
        cache_hit: bool,
        confidence_score: Any,
        selected_chunks: list[dict],
        user_id: int | None = None,
        username: str | None = None,
    ) -> None:
        if not self.database.configured:
            return
        try:
            with self.database.connection() as conn:
                row = conn.execute(
                    load_query("query_log_insert.sql"),
                    (
                        user_id,
                        username,
                        model_name,
                        retrieval_strategy,
                        question,
                        retrieval_query,
                        elapsed_ms,
                        cache_hit,
                        self._optional_float(confidence_score),
                    ),
                ).fetchone()
                query_log_id = row["id"]
                for rank, chunk in enumerate(selected_chunks, start=1):
                    source = chunk.get("source") or "Unknown"
                    db_source = self._db_source_path(source)
                    conn.execute(
                        load_query("query_log_source_insert.sql"),
                        (
                            query_log_id,
                            rank,
                            db_source,
                            os.path.basename(source),
                            db_source,
                            os.path.basename(source),
                            chunk.get("index"),
                            source,
                            chunk.get("page"),
                            self._optional_float(chunk.get("distance")),
                        ),
                    )
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"DB query log write failed: {exc}")

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _db_source_path(source: str) -> str:
        if source.startswith("training" + os.sep):
            return os.path.relpath(source, "training")
        return source
