"""Structured response cache key and entry types."""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Any


CACHE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ResponseCacheKey:
    entity_id: int | None
    index_fingerprint: str
    model: str
    strategy: str
    question: str
    retrieval_query: str
    top_k: int
    distance_threshold: float
    max_tokens: int
    show_full_text: bool
    schema_version: int = CACHE_SCHEMA_VERSION
    kind: str = "rag-response"

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        serialized = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass
class ResponseCacheEntry:
    answer: str
    chat_history: list[list[str]]
    sources: list[Any]
    confidence: str
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class ResponseCache:
    def __init__(self, capacity: int = 200, trace_logger=None):
        self.entries: OrderedDict[str, ResponseCacheEntry] = OrderedDict()
        self.capacity = capacity
        self.hits = 0
        self.misses = 0
        self.trace_logger = trace_logger

    def get_response(self, key: ResponseCacheKey) -> ResponseCacheEntry | None:
        digest = key.digest()
        if digest not in self.entries:
            self.misses += 1
            if self.trace_logger:
                self.trace_logger.debug(f"Response cache MISS for key: {digest}")
            return None

        self.entries.move_to_end(digest)
        self.hits += 1
        if self.trace_logger:
            self.trace_logger.debug(f"Response cache HIT for key: {digest}")
        return self.entries[digest]

    def put_response(self, key: ResponseCacheKey, entry: ResponseCacheEntry) -> None:
        digest = key.digest()
        if digest in self.entries:
            self.entries.move_to_end(digest)
        self.entries[digest] = entry
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)

    def clear(self) -> None:
        self.entries.clear()

    def stats(self) -> dict[str, int]:
        return {
            "size": len(self.entries),
            "capacity": self.capacity,
            "hits": self.hits,
            "misses": self.misses,
        }

    # Compatibility for old call sites while the old UI code still exists.
    def get(self, key):
        if isinstance(key, ResponseCacheKey):
            return self.get_response(key)
        self.misses += 1
        return None

    def put(self, key, value):
        if isinstance(key, ResponseCacheKey) and isinstance(value, ResponseCacheEntry):
            self.put_response(key, value)


def has_chat_history(chat_history: Any) -> bool:
    return bool(chat_history)


def should_cache_response(chat_history: Any, bypass_cache: bool) -> bool:
    return not bypass_cache and not has_chat_history(chat_history)
