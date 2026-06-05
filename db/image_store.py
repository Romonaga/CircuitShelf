from __future__ import annotations

import base64
import hashlib
import os
import re
from collections import defaultdict
from io import BytesIO
from typing import Any

from PIL import Image
from psycopg.errors import UndefinedColumn, UndefinedTable

from db.connection import Database
from db.sql import load_query
from db.text import clean_db_text
from db.vector_store import vector_to_sql
from backend.ingestion.manifest import FileRecord


class ImageStore:
    def __init__(self, database: Database, training_dir: str, logger=None):
        self.database = database
        self.training_dir = training_dir
        self.logger = logger

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("image_load.sql")).fetchone()
            return True
        except (UndefinedTable, UndefinedColumn):
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Image store is not available: {exc}")
            return False

    def replace_catalog(
        self,
        *,
        file_records: dict[str, FileRecord],
        image_store: dict[str, str],
        image_captions: dict[str, str],
        image_page_text: dict[str, str],
        image_embeddings: dict[str, Any],
        embedding_model: str,
        metadata: list[dict],
        progress_callback=None,
    ) -> None:
        if not image_store:
            with self.database.connection() as conn:
                conn.execute(load_query("image_catalog_clear.sql"))
                self._refresh_document_image_stats(conn, None)
            return

        with self.database.connection() as conn:
            conn.execute(load_query("image_catalog_clear.sql"))
        doc_rows = self._load_image_documents()
        rows, refreshed_paths, skipped_images = self._prepare_image_insert_rows(
            doc_rows,
            file_records=file_records,
            image_store=image_store,
            image_captions=image_captions,
            image_page_text=image_page_text,
            image_embeddings=image_embeddings,
            embedding_model=embedding_model,
            metadata=metadata,
            progress_callback=progress_callback,
        )
        with self.database.connection() as conn:
            self._insert_image_rows(
                conn,
                rows,
                total_images=len(image_store),
                initial_skipped_images=skipped_images,
                progress_callback=progress_callback,
            )
            self._refresh_document_image_stats(conn, None)

    def upsert_sources(
        self,
        *,
        file_records: dict[str, FileRecord],
        image_store: dict[str, str],
        image_captions: dict[str, str],
        image_page_text: dict[str, str],
        image_embeddings: dict[str, Any],
        embedding_model: str,
        metadata: list[dict],
        rel_paths: set[str],
        progress_callback=None,
    ) -> None:
        if not image_store:
            return
        doc_rows = self._load_image_documents()
        rows, refreshed_paths, skipped_images = self._prepare_image_insert_rows(
            doc_rows,
            file_records=file_records,
            image_store=image_store,
            image_captions=image_captions,
            image_page_text=image_page_text,
            image_embeddings=image_embeddings,
            embedding_model=embedding_model,
            metadata=metadata,
            rel_paths=rel_paths,
            progress_callback=progress_callback,
        )
        if not rows and not refreshed_paths:
            return
        with self.database.connection() as conn:
            self._insert_image_rows(
                conn,
                rows,
                total_images=len(image_store),
                initial_skipped_images=skipped_images,
                progress_callback=progress_callback,
            )
            self._refresh_document_image_stats(conn, refreshed_paths)

    def _load_image_documents(self):
        with self.database.connection() as conn:
            return conn.execute(load_query("image_document_map.sql")).fetchall()

    def _prepare_image_insert_rows(
        self,
        doc_rows,
        *,
        file_records: dict[str, FileRecord],
        image_store: dict[str, str],
        image_captions: dict[str, str],
        image_page_text: dict[str, str],
        image_embeddings: dict[str, Any],
        embedding_model: str,
        metadata: list[dict],
        rel_paths: set[str] | None = None,
        progress_callback=None,
    ) -> tuple[list[tuple], set[str], int]:
        image_meta = self._metadata_by_image_key(metadata)
        documents = self._document_lookup(doc_rows)
        ordinals: dict[str, int] = defaultdict(int)
        total_images = len(image_store)
        prepared_images = 0
        skipped_images = 0
        refreshed_paths: set[str] = set(rel_paths or [])
        rows: list[tuple] = []

        for image_key, image_base64 in sorted(image_store.items()):
            rel_path, page_number, score, confidence = self._resolve_image_document(
                image_key,
                image_meta.get(image_key, {}),
                file_records,
                documents,
            )
            if rel_paths is not None and rel_path not in rel_paths:
                skipped_images += 1
                continue
            doc_row = documents.get(rel_path)
            if not doc_row:
                skipped_images += 1
                if self.logger:
                    self.logger.warning(f"Skipping image without indexed document: {image_key}")
                continue

            try:
                image_bytes = base64.b64decode(image_base64)
            except Exception as exc:
                skipped_images += 1
                if self.logger:
                    self.logger.warning(f"Skipping invalid image asset {image_key}: {exc}")
                continue
            stored_image_bytes, mime_type, width, height = self._prepare_image_for_storage(image_bytes)
            ordinals[rel_path] += 1
            ordinal = ordinals[rel_path]
            refreshed_paths.add(rel_path)
            rows.append(
                (
                    doc_row["id"],
                    doc_row["id"],
                    page_number,
                    clean_db_text(image_key),
                    ordinal,
                    stored_image_bytes,
                    clean_db_text(mime_type),
                    width,
                    height,
                    clean_db_text(image_captions.get(image_key, image_key)),
                    clean_db_text(image_page_text.get(image_key, "")),
                    score,
                    confidence,
                    hashlib.sha256(stored_image_bytes).hexdigest(),
                    clean_db_text(embedding_model),
                    vector_to_sql(image_embeddings[image_key]) if image_key in image_embeddings else None,
                )
            )
            prepared_images += 1
            if progress_callback and (prepared_images == 1 or prepared_images % 100 == 0 or prepared_images + skipped_images >= total_images):
                progress_callback(
                    prepared_images=prepared_images,
                    total_images=total_images,
                    skipped_images=skipped_images,
                    current_image=image_key,
                )
        return rows, refreshed_paths, skipped_images

    def _insert_image_rows(
        self,
        conn,
        rows: list[tuple],
        *,
        total_images: int,
        initial_skipped_images: int = 0,
        progress_callback=None,
    ) -> None:
        stored_images = 0
        skipped_images = initial_skipped_images
        query = load_query("image_insert.sql")
        for row in rows:
            conn.execute(query, row)
            stored_images += 1
            if progress_callback and (stored_images == 1 or stored_images % 100 == 0 or stored_images + skipped_images >= total_images):
                progress_callback(
                    saved_images=stored_images,
                    total_images=total_images,
                    skipped_images=skipped_images,
                    current_image=row[3],
                )

    def _refresh_document_image_stats(self, conn, rel_paths: set[str] | None) -> None:
        paths = sorted(rel_paths) if rel_paths is not None else None
        conn.execute(load_query("document_image_stats_refresh.sql"), (paths, paths, paths, paths))

    def counts(self) -> dict[str, int]:
        with self.database.connection() as conn:
            row = conn.execute(load_query("image_catalog_counts.sql")).fetchone()
        return {
            "stored": int(row["stored_images"] or 0),
            "embeddings": int(row["embeddings"] or 0),
            "referenced": int(row["referenced_images"] or 0),
        }

    def load_missing_embedding_inputs(self, *, limit: int = 256) -> list[dict]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("image_missing_embeddings_load.sql"), (int(limit),)).fetchall()
        return [dict(row) for row in rows]

    def update_embeddings(self, image_embeddings: dict[str, Any], embedding_model: str) -> None:
        if not image_embeddings:
            return
        with self.database.connection() as conn:
            for image_key, embedding in image_embeddings.items():
                conn.execute(
                    load_query("image_embedding_update.sql"),
                    (embedding_model, vector_to_sql(embedding), image_key),
                )

    def has_missing_catalog_entries(self) -> bool:
        if not self.available():
            return False
        counts = self.counts()
        return counts["referenced"] > counts["stored"] or counts["stored"] > counts["embeddings"]

    def search_images(self, query_embedding, *, top_k: int, entity_id: int | None = None) -> list[dict]:
        vector = vector_to_sql(query_embedding)
        with self.database.connection() as conn:
            rows = conn.execute(load_query("image_search.sql"), (vector, entity_id, vector, int(top_k))).fetchall()
        return [dict(row) for row in rows]

    def load_state_payload(self) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("image_load.sql")).fetchall()

        image_store: dict[str, str] = {}
        captions: dict[str, str] = {}
        page_text: dict[str, str] = {}
        mime_types: dict[str, str] = {}
        for row in rows:
            key = row["image_key"]
            image_store[key] = row["image_base64"]
            captions[key] = row["caption"] or key
            page_text[key] = row["ocr_text"] or ""
            mime_types[key] = row["image_mime_type"] or "image/png"
        return image_store, captions, page_text, mime_types

    def list_review_images(self, source_path: str) -> list[dict]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("review_document_images.sql"), (source_path,)).fetchall()
        return [dict(row) for row in rows]

    def list_document_images(self, source_path: str) -> list[dict]:
        return self.list_review_images(source_path)

    def delete_document_images(self, source_path: str) -> None:
        with self.database.connection() as conn:
            conn.execute(load_query("review_document_images_delete.sql"), (source_path, source_path))

    def _metadata_by_image_key(self, metadata: list[dict]) -> dict[str, dict]:
        result = {}
        for meta in metadata:
            image_key = (meta or {}).get("source_image_id")
            if image_key and image_key not in result:
                result[image_key] = meta
        return result

    def _resolve_image_document(
        self,
        image_key: str,
        meta: dict[str, Any],
        file_records: dict[str, FileRecord],
        documents: dict[str, dict],
    ) -> tuple[str | None, int | None, float | None, float | None]:
        rel_path = self.rel_path_for_source(meta.get("parent_source") or meta.get("source") or image_key)
        if rel_path not in documents:
            rel_path = self._rel_path_from_image_key(image_key, file_records, documents)
        page_number = self._page_number(meta) or self._page_number_from_image_key(image_key)
        score = self._optional_float(meta.get("ocr_score"))
        confidence = self._optional_float(meta.get("ocr_confidence"))
        return rel_path, page_number, score, confidence

    def _rel_path_from_image_key(
        self,
        image_key: str,
        file_records: dict[str, FileRecord],
        documents: dict[str, dict],
    ) -> str | None:
        if image_key in documents:
            return image_key
        for rel_path in file_records:
            base = os.path.basename(rel_path)
            if image_key == base or image_key.startswith(f"{base}_page") or image_key.startswith(f"{base}_textbox"):
                return rel_path
        for rel_path, row in documents.items():
            display_name = row["display_name"]
            if image_key == display_name or image_key.startswith(f"{display_name}_page") or image_key.startswith(f"{display_name}_textbox"):
                return rel_path
        return None

    def _document_lookup(self, rows) -> dict[str, dict]:
        documents = {}
        for row in rows:
            documents[row["source_path"]] = dict(row)
        return documents

    def rel_path_for_source(self, source: str) -> str:
        candidate = os.path.normpath(str(source))
        training_dir = os.path.normpath(self.training_dir)
        if candidate.startswith(training_dir + os.sep):
            return os.path.relpath(candidate, training_dir)
        if os.path.isabs(candidate):
            try:
                return os.path.relpath(candidate, training_dir)
            except ValueError:
                return os.path.basename(candidate)
        return candidate

    @staticmethod
    def _page_number(meta: dict[str, Any]) -> int | None:
        value = meta.get("page")
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _page_number_from_image_key(image_key: str) -> int | None:
        match = re.search(r"_page(\d+)", image_key)
        return int(match.group(1)) if match else None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _image_size(image_bytes: bytes) -> tuple[int | None, int | None]:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                return image.size
        except Exception:
            return None, None

    def _prepare_image_for_storage(self, image_bytes: bytes) -> tuple[bytes, str, int | None, int | None]:
        width, height = self._image_size(image_bytes)
        optimized = self._to_webp(image_bytes)
        if optimized is not None:
            if self.logger:
                saved = len(image_bytes) - len(optimized)
                direction = "Compressed" if saved >= 0 else "Canonicalized"
                suffix = f"({saved / max(1, len(image_bytes)):.1%} smaller)" if saved >= 0 else f"({abs(saved)} bytes larger)"
                self.logger.debug(f"{direction} image asset from {len(image_bytes)} to {len(optimized)} bytes {suffix}.")
            return optimized, "image/webp", width, height
        return image_bytes, self._detect_mime_type(image_bytes), width, height

    @staticmethod
    def _to_webp(image_bytes: bytes) -> bytes | None:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
                output = BytesIO()
                if has_alpha:
                    converted = image.convert("RGBA")
                    converted.save(output, format="WEBP", lossless=True, method=6)
                else:
                    converted = image.convert("RGB")
                    converted.save(output, format="WEBP", quality=82, method=6)
                candidate = output.getvalue()
        except Exception:
            return None
        return candidate or None

    @staticmethod
    def _detect_mime_type(image_bytes: bytes) -> str:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image_format = (image.format or "").upper()
        except Exception:
            return "application/octet-stream"
        if image_format == "JPEG":
            return "image/jpeg"
        if image_format == "WEBP":
            return "image/webp"
        if image_format == "PNG":
            return "image/png"
        return f"image/{image_format.lower()}" if image_format else "application/octet-stream"
