from __future__ import annotations

import os
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from psycopg.errors import UndefinedColumn, UndefinedTable

from db.connection import Database
from db.sql import load_query
from db.text import clean_db_text
from backend.ingestion.manifest import FileRecord


def vector_to_sql(value: Any) -> str:
    array = np.asarray(value, dtype="float32").reshape(-1)
    return "[" + ",".join(f"{float(item):.8g}" for item in array.tolist()) + "]"


def vector_from_sql(value: str | None) -> np.ndarray | None:
    if not value:
        return None
    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]
    if not stripped:
        return None
    return np.asarray([float(item) for item in stripped.split(",")], dtype="float32")


def bool_from_meta(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


class VectorStore:
    def __init__(self, database: Database, training_dir: str, embedding_model: str, logger=None):
        self.database = database
        self.training_dir = training_dir
        self.embedding_model = embedding_model
        self.logger = logger

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            self.counts()
            return True
        except (UndefinedTable, UndefinedColumn):
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Vector store is not available: {exc}")
            return False

    def load_document_records(self) -> dict[str, FileRecord]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("vector_catalog_document_records.sql")).fetchall()
        return {
            row["path"]: FileRecord(
                path=row["path"],
                size=int(row["size"]),
                mtime_ns=int(row["mtime_ns"]),
                sha256=row["sha256"],
            )
            for row in rows
        }

    def find_document_sources_by_term(self, term: str, *, limit: int = 5) -> list[str]:
        pattern = f"%{term}%"
        with self.database.connection() as conn:
            rows = conn.execute(load_query("vector_documents_find_by_term.sql"), (pattern, pattern, int(limit))).fetchall()
        return [row["source_path"] for row in rows]

    def counts(self, *, entity_id: int | None = None) -> dict[str, int]:
        with self.database.connection() as conn:
            row = conn.execute(load_query("vector_catalog_counts.sql"), (entity_id, entity_id, entity_id)).fetchone()
        return {
            "documents": int(row["documents"] or 0),
            "chunks": int(row["chunks"] or 0),
            "embeddings": int(row["embeddings"] or 0),
        }

    def pending_review_count(self) -> int:
        with self.database.connection() as conn:
            row = conn.execute(load_query("review_pending_count.sql")).fetchone()
        return int(row["pending"] or 0)

    def catalog_fingerprint(self, *, entity_id: int | None = None) -> str:
        with self.database.connection() as conn:
            row = conn.execute(load_query("vector_catalog_fingerprint.sql"), (entity_id,)).fetchone()
        payload = row["fingerprint_source"] or ""
        digest = hashlib.sha256()
        digest.update(payload.encode("utf-8"))
        return digest.hexdigest()

    def clear(self) -> None:
        with self.database.connection() as conn:
            conn.execute(load_query("vector_catalog_clear.sql"))

    def delete_sources(self, rel_paths: list[str]) -> None:
        if not rel_paths:
            return
        with self.database.connection() as conn:
            conn.execute(load_query("vector_document_delete_by_sources.sql"), (rel_paths,))

    def set_ingest_scope(
        self,
        source_path: str,
        *,
        entity_id: int | None,
        is_global: bool,
        created_by_user_id: int | None = None,
    ) -> dict:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("document_ingest_scope_upsert.sql"),
                (
                    clean_db_text(source_path),
                    None if entity_id is None else int(entity_id),
                    bool(is_global),
                    None if created_by_user_id is None else int(created_by_user_id),
                ),
            ).fetchone()
        return dict(row)

    def ingest_scope_overrides(self, source_paths: list[str]) -> dict[str, dict[str, Any]]:
        if not source_paths:
            return {}
        with self.database.connection() as conn:
            rows = conn.execute(load_query("document_ingest_scope_get_many.sql"), (source_paths,)).fetchall()
        return {row["source_path"]: dict(row) for row in rows}

    def document_scopes_for_sources(self, source_paths: list[str]) -> dict[str, dict[str, Any]]:
        if not source_paths:
            return {}
        with self.database.connection() as conn:
            rows = conn.execute(load_query("vector_document_scope_get_many.sql"), (source_paths,)).fetchall()
        return {row["source_path"]: dict(row) for row in rows}

    def replace_catalog(
        self,
        *,
        file_records: dict[str, FileRecord],
        chunks: list[str],
        sources: list[str],
        metadata: list[dict],
        embeddings: np.ndarray,
        status: str = "indexed",
        document_stats: dict[str, dict[str, int]] | None = None,
    ) -> None:
        if len(chunks) != len(sources) or len(chunks) != len(metadata) or len(chunks) != len(embeddings):
            raise ValueError("Chunk, source, metadata, and embedding counts must match before DB persistence.")

        with self.database.connection() as conn:
            conn.execute(load_query("vector_catalog_clear.sql"))
            self._insert_catalog_rows(conn, file_records, chunks, sources, metadata, embeddings, status, document_stats or {}, None)

    def replace_sources(
        self,
        *,
        delete_rel_paths: list[str],
        file_records: dict[str, FileRecord],
        chunks: list[str],
        sources: list[str],
        metadata: list[dict],
        embeddings: np.ndarray,
        status: str = "needs_review",
        document_stats: dict[str, dict[str, int]] | None = None,
        scope_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        if len(chunks) != len(sources) or len(chunks) != len(metadata) or len(chunks) != len(embeddings):
            raise ValueError("Chunk, source, metadata, and embedding counts must match before DB persistence.")

        with self.database.connection() as conn:
            persisted_scopes = self.document_scopes_for_sources(delete_rel_paths)
            effective_scopes = {
                **persisted_scopes,
                **(scope_overrides or self.ingest_scope_overrides(list(file_records.keys()))),
            }
            if delete_rel_paths:
                conn.execute(load_query("vector_document_delete_by_sources.sql"), (delete_rel_paths,))
            self._insert_catalog_rows(conn, file_records, chunks, sources, metadata, embeddings, status, document_stats or {}, effective_scopes)

    def _insert_catalog_rows(
        self,
        conn,
        file_records: dict[str, FileRecord],
        chunks: list[str],
        sources: list[str],
        metadata: list[dict],
        embeddings: np.ndarray,
        status: str,
        document_stats: dict[str, dict[str, int]],
        scope_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        document_ids: dict[str, str] = {}
        page_ids: dict[tuple[str, int], str] = {}
        next_chunk_index: dict[str, int] = {}

        for chunk, source, meta, embedding in zip(chunks, sources, metadata, embeddings):
            rel_path = self.rel_path_for_source(source, meta)
            record = file_records.get(rel_path) or self.record_from_source(rel_path)
            document_id = document_ids.get(rel_path)
            if not document_id:
                stats = document_stats.get(rel_path, {})
                scope = (scope_overrides or {}).get(rel_path, {})
                is_global = bool(scope.get("is_global", True))
                entity_id = None if is_global else scope.get("entity_id")
                document_id = conn.execute(
                    load_query("vector_document_upsert.sql"),
                    (
                        clean_db_text(rel_path),
                        clean_db_text(os.path.basename(rel_path)),
                        clean_db_text(Path(rel_path).suffix.lower()),
                        record.size,
                        record.mtime_ns,
                        clean_db_text(record.sha256, None),
                        clean_db_text(status),
                        None if stats.get("pageCount") is None else int(stats.get("pageCount") or 0),
                        int(stats.get("rawChunkCount", 0) or 0),
                        int(stats.get("chunkCount", 0) or 0),
                        int(stats.get("droppedChunkCount", 0) or 0),
                        int(stats.get("extractedImageCount", 0) or 0),
                        int(stats.get("indexedImageTextCount", 0) or 0),
                        int(stats.get("ocrImageTextCount", 0) or 0),
                        None if entity_id is None else int(entity_id),
                        is_global,
                        None if scope.get("created_by_user_id") is None else int(scope["created_by_user_id"]),
                    ),
                ).fetchone()["id"]
                document_ids[rel_path] = document_id

            page_number = self.page_number(meta)
            page_id = None
            if page_number is not None:
                page_key = (rel_path, page_number)
                page_id = page_ids.get(page_key)
                if not page_id:
                    page_id = conn.execute(
                        load_query("vector_page_upsert.sql"),
                        (document_id, page_number),
                    ).fetchone()["id"]
                    page_ids[page_key] = page_id

            chunk_index = next_chunk_index.get(rel_path, 0)
            next_chunk_index[rel_path] = chunk_index + 1
            meta["db_source_path"] = rel_path
            meta["db_chunk_index"] = chunk_index
            chunk_id = conn.execute(
                load_query("vector_chunk_insert.sql"),
                (
                    document_id,
                    page_id,
                    chunk_index,
                    clean_db_text(chunk),
                    int(meta.get("token_count") or 0),
                    clean_db_text(meta.get("section") or "Unknown"),
                    clean_db_text(meta.get("category") or "Uncategorized"),
                    float(meta.get("quality_score", 0.0) or 0.0),
                    bool_from_meta(meta.get("chunk_type") == "ocr" or meta.get("is_ocr")),
                    bool_from_meta(meta.get("has_math")),
                    clean_db_text(meta.get("source_image_id"), None),
                    clean_db_text(self.embedding_model),
                    vector_to_sql(embedding),
                ),
            ).fetchone()["id"]

            for flag in meta.get("quality_flags") or []:
                conn.execute(load_query("vector_quality_flag_insert.sql"), (chunk_id, clean_db_text(flag)))

    def load_state_payload(self) -> tuple[list[str], list[str], list[dict], list[np.ndarray]]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("vector_chunks_load.sql")).fetchall()

        chunks: list[str] = []
        sources: list[str] = []
        metadata: list[dict] = []
        embeddings: list[np.ndarray] = []
        for row in rows:
            source = os.path.join(self.training_dir, row["source_path"])
            chunks.append(row["chunk_text"])
            sources.append(source)
            meta = {
                "section": row["section_title"] or "Unknown",
                "page": row["page_number"] or 1,
                "source": source,
                "parent_source": source,
                "category": row["category"] or "Uncategorized",
                "chunk_type": "ocr" if row["is_ocr"] else "paragraph",
                "token_count": int(row["token_count"] or 0),
                "quality_score": float(row["quality_score"] or 0.0),
                "quality_flags": list(row["quality_flags"] or []),
                "has_math": bool(row["has_math"]),
                "db_source_path": row["source_path"],
                "db_chunk_index": int(row["chunk_index"]),
            }
            if row["source_image_key"]:
                meta["source_image_id"] = row["source_image_key"]
            metadata.append(meta)
            embedding = vector_from_sql(row["embedding"])
            if embedding is not None:
                embeddings.append(embedding)

        return chunks, sources, metadata, embeddings

    def search_chunks(self, query_embedding: np.ndarray, *, top_k: int, entity_id: int | None = None) -> list[dict]:
        vector = vector_to_sql(query_embedding)
        with self.database.connection() as conn:
            rows = conn.execute(load_query("vector_search_chunks.sql"), (vector, entity_id, vector, int(top_k))).fetchall()

        results = []
        for row in rows:
            source = os.path.join(self.training_dir, row["source_path"])
            results.append({
                "source": source,
                "chunk_index": int(row["chunk_index"]),
                "text": row["chunk_text"],
                "distance": float(row["distance"]),
                "section": row["section_title"] or "Unknown",
                "page": row["page_number"],
                "category": row["category"] or "Uncategorized",
                "source_image_id": row["source_image_key"],
            })
        return results

    def list_review_documents(self, *, scope: str = "all", entity_id: int | None = None) -> list[dict]:
        scope = scope if scope in {"all", "global", "entity"} else "all"
        with self.database.connection() as conn:
            rows = conn.execute(load_query("review_documents_list.sql"), (scope, scope, scope, entity_id)).fetchall()
        return [dict(row) for row in rows]

    def get_document_scope(self, source_path: str) -> dict | None:
        with self.database.connection() as conn:
            row = conn.execute(load_query("document_scope_get.sql"), (source_path,)).fetchone()
        return dict(row) if row else None

    def document_scope_audit(self, source_path: str, *, limit: int = 25) -> list[dict]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("document_scope_audit_list.sql"), (source_path, max(1, min(int(limit), 100)))).fetchall()
        return [dict(row) for row in rows]

    def set_document_scope(
        self,
        source_path: str,
        *,
        is_global: bool,
        entity_id: int | None,
        changed_by_user_id: int | None,
        reason: str = "",
    ) -> dict | None:
        previous = self.get_document_scope(source_path)
        if not previous:
            return None
        next_entity_id = None if is_global else entity_id
        if not is_global and next_entity_id is None:
            raise ValueError("Private document scope requires an entity.")
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("document_scope_update.sql"),
                (bool(is_global), next_entity_id, source_path),
            ).fetchone()
            conn.execute(
                load_query("document_ingest_scope_upsert.sql"),
                (
                    source_path,
                    next_entity_id,
                    bool(is_global),
                    changed_by_user_id,
                ),
            )
            conn.execute(
                load_query("document_scope_audit_insert.sql"),
                (
                    source_path,
                    previous.get("is_global"),
                    previous.get("entity_id"),
                    bool(is_global),
                    next_entity_id,
                    changed_by_user_id,
                    clean_db_text(reason or "scope change"),
                ),
            )
        return dict(row) if row else None

    def list_document_stats(self, *, entity_id: int | None = None, scope: str = "visible") -> list[dict]:
        scope = "global" if scope == "global" else "visible"
        with self.database.connection() as conn:
            rows = conn.execute(load_query("vector_documents_stats.sql"), (scope, scope, entity_id)).fetchall()
        return [dict(row) for row in rows]

    def review_document_chunks(self, source_path: str, *, limit: int = 50) -> list[dict]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("review_document_chunks.sql"), (source_path, int(limit))).fetchall()
        return [dict(row) for row in rows]

    def set_document_status(self, source_path: str, status: str, reviewed_by: str | None) -> dict | None:
        with self.database.connection() as conn:
            row = conn.execute(load_query("review_document_status_update.sql"), (status, reviewed_by, source_path)).fetchone()
        return dict(row) if row else None

    def set_sources_status(self, source_paths: list[str], status: str) -> list[str]:
        if not source_paths:
            return []
        with self.database.connection() as conn:
            rows = conn.execute(load_query("review_documents_status_update_by_sources.sql"), (status, source_paths)).fetchall()
        return [row["source_path"] for row in rows]

    def delete_document(self, source_path: str) -> dict | None:
        with self.database.connection() as conn:
            row = conn.execute(load_query("review_document_delete.sql"), (source_path,)).fetchone()
        return dict(row) if row else None

    def rel_path_for_source(self, source: str, meta: dict | None = None) -> str:
        meta = meta or {}
        candidate = meta.get("parent_source") or meta.get("source") or source
        candidate = os.path.normpath(str(candidate))
        training_dir = os.path.normpath(self.training_dir)
        if candidate.startswith(training_dir + os.sep):
            return os.path.relpath(candidate, training_dir)
        if os.path.isabs(candidate):
            try:
                return os.path.relpath(candidate, training_dir)
            except ValueError:
                return os.path.basename(candidate)
        return candidate

    def record_from_source(self, rel_path: str) -> FileRecord:
        full_path = os.path.join(self.training_dir, rel_path)
        if os.path.exists(full_path):
            stat = os.stat(full_path)
            return FileRecord(path=rel_path, size=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=None)
        return FileRecord(path=rel_path, size=0, mtime_ns=0, sha256=None)

    @staticmethod
    def page_number(meta: dict) -> int | None:
        value = meta.get("page")
        if value is None:
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None
