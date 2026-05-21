from __future__ import annotations

import os
from collections import OrderedDict
from typing import Any

from psycopg.errors import UndefinedColumn, UndefinedTable

from db.connection import Database
from db.sql import load_query
from response_cache import ResponseCacheEntry, ResponseCacheKey


class PostgresResponseCache:
    def __init__(self, database: Database, *, capacity: int = 200, logger=None):
        self.database = database
        self.capacity = capacity
        self.logger = logger
        self.hits = 0
        self.misses = 0

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            self._size()
            return True
        except (UndefinedTable, UndefinedColumn):
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"DB response cache is not available: {exc}")
            return False

    def get_response(self, key: ResponseCacheKey) -> ResponseCacheEntry | None:
        digest = key.digest()
        try:
            with self.database.connection() as conn:
                row = conn.execute(
                    load_query("response_cache_entry_get.sql"),
                    (
                        digest,
                        key.index_fingerprint,
                        key.model,
                        key.strategy,
                        key.question,
                        key.retrieval_query,
                        key.top_k,
                        key.distance_threshold,
                        key.max_tokens,
                        key.show_full_text,
                    ),
                ).fetchone()
                if not row:
                    self.misses += 1
                    return None

                conn.execute(load_query("response_cache_entry_touch.sql"), (row["id"],))
                turns = conn.execute(load_query("response_cache_turns_load.sql"), (row["id"],)).fetchall()
                sources = conn.execute(load_query("response_cache_sources_load.sql"), (row["id"],)).fetchall()

            self.hits += 1
            return ResponseCacheEntry(
                answer=row["answer_markdown"],
                chat_history=[[turn["user_message"], turn["assistant_message"]] for turn in turns],
                sources=self._group_sources(sources),
                confidence=self._confidence_to_string(row["confidence_score"]),
            )
        except Exception as exc:
            self.misses += 1
            if self.logger:
                self.logger.warning(f"DB response cache read failed: {exc}")
            return None

    def put_response(self, key: ResponseCacheKey, entry: ResponseCacheEntry) -> None:
        digest = key.digest()
        try:
            with self.database.connection() as conn:
                row = conn.execute(
                    load_query("response_cache_entry_upsert.sql"),
                    (
                        digest,
                        key.index_fingerprint,
                        key.model,
                        key.strategy,
                        key.question,
                        key.retrieval_query,
                        key.top_k,
                        key.distance_threshold,
                        key.max_tokens,
                        key.show_full_text,
                        entry.answer,
                        self._optional_float(entry.confidence),
                    ),
                ).fetchone()
                entry_id = row["id"]

                conn.execute(load_query("response_cache_turns_clear.sql"), (entry_id,))
                for index, turn in enumerate(entry.chat_history):
                    if len(turn) < 2:
                        continue
                    conn.execute(
                        load_query("response_cache_turn_insert.sql"),
                        (entry_id, index, str(turn[0]), str(turn[1])),
                    )

                conn.execute(load_query("response_cache_sources_clear.sql"), (entry_id,))
                for rank, source in enumerate(self._flatten_sources(entry.sources), start=1):
                    conn.execute(
                        load_query("response_cache_source_insert.sql"),
                        (
                            entry_id,
                            rank,
                            self._db_source_path(source["source"]),
                            os.path.basename(source["source"]),
                            self._db_source_path(source["source"]),
                            os.path.basename(source["source"]),
                            source.get("index"),
                            source["source"],
                            source.get("page"),
                            self._optional_float(source.get("distance")),
                            source.get("preview", ""),
                            source.get("index"),
                            source.get("section", "Unknown"),
                            source.get("category", "Uncategorized"),
                            source.get("sourceImageId"),
                        ),
                    )

                conn.execute(load_query("response_cache_evict.sql"), (self.capacity,))
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"DB response cache write failed: {exc}")

    def stats(self) -> dict[str, int]:
        return {
            "size": self._size(),
            "capacity": self.capacity,
            "hits": self.hits,
            "misses": self.misses,
        }

    def clear(self) -> None:
        if self.logger:
            self.logger.warning("DB response cache clear requested but no destructive clear is wired to the UI.")

    def get(self, key):
        if isinstance(key, ResponseCacheKey):
            return self.get_response(key)
        self.misses += 1
        return None

    def put(self, key, value):
        if isinstance(key, ResponseCacheKey) and isinstance(value, ResponseCacheEntry):
            self.put_response(key, value)

    def _size(self) -> int:
        with self.database.connection() as conn:
            row = conn.execute(load_query("response_cache_count.sql")).fetchone()
        return int(row["size"] or 0)

    def _flatten_sources(self, sources: list[Any]) -> list[dict]:
        rows = []
        for source in sources or []:
            if isinstance(source, str):
                rows.append({
                    "source": source,
                    "page": None,
                    "distance": None,
                    "preview": "",
                    "index": None,
                    "section": "Unknown",
                    "category": "Uncategorized",
                    "sourceImageId": None,
                })
                continue
            for chunk in source.get("chunks", []):
                rows.append({
                    "source": source.get("source", "Unknown"),
                    "page": chunk.get("page"),
                    "distance": chunk.get("distance"),
                    "preview": chunk.get("preview", ""),
                    "index": chunk.get("index"),
                    "section": chunk.get("section", "Unknown"),
                    "category": chunk.get("category", "Uncategorized"),
                    "sourceImageId": chunk.get("sourceImageId"),
                })
        return rows

    def _group_sources(self, rows) -> list[dict]:
        grouped = OrderedDict()
        for row in rows:
            source = row["source_path"]
            doc = grouped.setdefault(
                source,
                {
                    "source": source,
                    "displayName": os.path.basename(source) if source else "Unknown",
                    "pages": [],
                    "chunkCount": 0,
                    "chunks": [],
                },
            )
            page = row["page_number"]
            if page is not None and page not in doc["pages"]:
                doc["pages"].append(page)
            doc["chunkCount"] += 1
            doc["chunks"].append({
                "index": row["chunk_index"],
                "page": page,
                "section": row["section_title"] or "Unknown",
                "category": row["category"] or "Uncategorized",
                "distance": float(row["distance"]) if row["distance"] is not None else None,
                "sourceImageId": row["source_image_key"],
                "preview": row["preview"] or "",
            })
        for doc in grouped.values():
            doc["pages"] = sorted(doc["pages"], key=lambda item: (not isinstance(item, (int, float)), item))
        return list(grouped.values())

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _confidence_to_string(value: Any) -> str:
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "0.00"

    @staticmethod
    def _db_source_path(source: str) -> str:
        if source.startswith("training" + os.sep):
            return os.path.relpath(source, "training")
        return source
