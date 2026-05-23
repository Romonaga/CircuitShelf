from __future__ import annotations

import os
import json
from typing import Any

from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query


class AssemblyPlanStore:
    def __init__(self, database: Database, training_dir: str, logger=None):
        self.database = database
        self.training_dir = training_dir
        self.logger = logger

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("assembly_plan_list.sql"), (None, None)).fetchone()
            return True
        except UndefinedTable:
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Assembly plan store is not available: {exc}")
            return False

    def create_from_card(self, *, question: str, card: dict[str, Any], user_id: int, created_by: str | None = None) -> dict:
        with self.database.connection() as conn:
            plan_id = conn.execute(
                load_query("assembly_plan_insert.sql"),
                (
                    card.get("title") or "Assembly plan",
                    question,
                    card.get("componentName") or "",
                    card.get("componentType") or "",
                    card.get("summary") or "",
                    self._optional_float(card.get("confidence")),
                    int(user_id),
                    int(user_id),
                ),
            ).fetchone()["id"]

            for ordinal, part in enumerate(card.get("parts") or [], start=1):
                conn.execute(
                    load_query("assembly_part_insert.sql"),
                    (plan_id, ordinal, part.get("name") or "", part.get("detail") or ""),
                )

            for ordinal, note in enumerate(card.get("power") or [], start=1):
                conn.execute(load_query("assembly_power_note_insert.sql"), (plan_id, ordinal, str(note)))

            sources = self._source_notes(card.get("sourceNotes") or [])
            source_for_page = self._source_for_page(sources)
            ordinal = 1
            for row in card.get("wiring") or []:
                source_path = source_for_page.get(self._optional_int(row.get("page"))) or (sources[0]["source_path"] if sources else None)
                conn.execute(
                    load_query("assembly_step_insert.sql"),
                    (
                        plan_id,
                        ordinal,
                        "wiring",
                        row.get("from") or f"Wiring step {ordinal}",
                        row.get("to") or "",
                        row.get("note") or "",
                        source_path,
                        self._optional_int(row.get("page")),
                    ),
                )
                ordinal += 1

            for check in card.get("checks") or []:
                conn.execute(
                    load_query("assembly_step_insert.sql"),
                    (plan_id, ordinal, "check", "Verification", str(check), "", None, None),
                )
                ordinal += 1

            for warning in card.get("warnings") or []:
                conn.execute(
                    load_query("assembly_step_insert.sql"),
                    (plan_id, ordinal, "warning", "Caution", str(warning), "", None, None),
                )
                ordinal += 1

            for source in sources:
                conn.execute(
                    load_query("assembly_source_insert.sql"),
                    (
                        plan_id,
                        source["source_path"],
                        source["display_name"],
                        source["pages"],
                        source["chunk_count"],
                    ),
                )
        return self.get(plan_id, user_id=user_id) or {}

    def list(self, user_id: int | None = None) -> list[dict]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("assembly_plan_list.sql"), (user_id, user_id)).fetchall()
        return [self._summary(row) for row in rows]

    def get(self, plan_id: str, user_id: int | None = None) -> dict | None:
        with self.database.connection() as conn:
            plan = conn.execute(load_query("assembly_plan_get.sql"), (plan_id, user_id, user_id)).fetchone()
            if not plan:
                return None
            parts = conn.execute(load_query("assembly_parts_get.sql"), (plan_id,)).fetchall()
            power = conn.execute(load_query("assembly_power_notes_get.sql"), (plan_id,)).fetchall()
            steps = conn.execute(load_query("assembly_steps_get.sql"), (plan_id,)).fetchall()
            sources = conn.execute(load_query("assembly_sources_get.sql"), (plan_id,)).fetchall()
            notes = conn.execute(load_query("assembly_notes_get.sql"), (plan_id,)).fetchall()

        step_payload = [self._step(row) for row in steps]
        return {
            **self._plan(plan),
            "stepCount": len(step_payload),
            "completedStepCount": sum(1 for step in step_payload if step["completed"]),
            "parts": [{"id": row["id"], "name": row["name"], "detail": row["detail"] or ""} for row in parts],
            "power": [{"id": row["id"], "note": row["note"]} for row in power],
            "steps": step_payload,
            "sources": [self._source(row) for row in sources],
            "notes": [self._note(row) for row in notes],
        }

    def delete(self, plan_id: str, user_id: int | None = None) -> dict | None:
        with self.database.connection() as conn:
            row = conn.execute(load_query("assembly_plan_delete.sql"), (plan_id, user_id, user_id)).fetchone()
        return {"id": row["id"], "title": row["title"]} if row else None

    def set_step_completed(self, plan_id: str, step_id: str, completed: bool, user_id: int | None = None) -> bool:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("assembly_step_completion_update.sql"),
                (bool(completed), step_id, plan_id, user_id, user_id),
            ).fetchone()
            if row:
                conn.execute(load_query("assembly_plan_touch.sql"), (plan_id,))
        return bool(row)

    def add_note(self, plan_id: str, role: str, message: str, user_id: int | None = None) -> dict:
        with self.database.connection() as conn:
            row = conn.execute(load_query("assembly_note_insert.sql"), (plan_id, role, message, plan_id, user_id, user_id)).fetchone()
            if row:
                conn.execute(load_query("assembly_plan_touch.sql"), (plan_id,))
        if not row:
            raise ValueError("Assembly plan not found.")
        return self._note(row)

    def evidence_for_step(self, plan_id: str, step_id: str, user_id: int, *, limit: int = 8) -> dict:
        with self.database.connection() as conn:
            chunks = conn.execute(
                load_query("assembly_step_evidence_chunks.sql"),
                (step_id, plan_id, user_id, user_id, int(limit)),
            ).fetchall()
            images = conn.execute(
                load_query("assembly_step_evidence_images.sql"),
                (step_id, plan_id, user_id, user_id, min(int(limit), 4)),
            ).fetchall()
        return {
            "chunks": [self._evidence_chunk(row) for row in chunks],
            "images": [self._evidence_image(row) for row in images],
        }

    def start_learning(self, plan_id: str, user_id: int) -> dict | None:
        with self.database.connection() as conn:
            row = conn.execute(load_query("assembly_learning_upsert.sql"), (user_id, plan_id, user_id)).fetchone()
        return self._learning(row) if row else None

    def get_learning(self, plan_id: str, user_id: int) -> dict | None:
        with self.database.connection() as conn:
            row = conn.execute(load_query("assembly_learning_get.sql"), (plan_id, user_id, user_id)).fetchone()
        return self._learning(row) if row else None

    def update_learning(self, plan_id: str, user_id: int, *, current_ordinal: int, mode_enabled: bool = True) -> dict | None:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("assembly_learning_update.sql"),
                (max(1, int(current_ordinal)), bool(mode_enabled), plan_id, user_id),
            ).fetchone()
        return self._learning(row) if row else None

    def add_photo_check(
        self,
        plan_id: str,
        user_id: int,
        *,
        image_mime_type: str,
        image_base64: str,
        note: str,
        checklist: str,
        diagnostics: dict | None = None,
    ) -> dict | None:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("assembly_photo_check_insert.sql"),
                (user_id, image_mime_type, image_base64, note, checklist, json.dumps(diagnostics or {}), plan_id, user_id),
            ).fetchone()
            if row:
                conn.execute(load_query("assembly_plan_touch.sql"), (plan_id,))
        return self._photo_check(row) if row else None

    def photo_checks(self, plan_id: str, user_id: int, *, limit: int = 10) -> list[dict]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("assembly_photo_checks_list.sql"), (plan_id, user_id, int(limit))).fetchall()
        return [self._photo_check(row) for row in rows]

    def _source_notes(self, raw_sources: list[dict]) -> list[dict]:
        result = []
        for source in raw_sources:
            source_path = self.rel_path_for_source(source.get("source") or source.get("displayName") or "")
            pages = []
            for page in source.get("pages") or []:
                page_number = self._optional_int(page)
                if page_number is not None and page_number not in pages:
                    pages.append(page_number)
            result.append(
                {
                    "source_path": source_path,
                    "display_name": source.get("displayName") or os.path.basename(source_path),
                    "pages": pages,
                    "chunk_count": int(source.get("chunks") or 0),
                }
            )
        return result

    def _source_for_page(self, sources: list[dict]) -> dict[int, str]:
        result = {}
        for source in sources:
            for page in source["pages"]:
                result.setdefault(page, source["source_path"])
        return result

    def rel_path_for_source(self, source: str) -> str:
        candidate = os.path.normpath(str(source or ""))
        training_dir = os.path.normpath(self.training_dir)
        if candidate.startswith(training_dir + os.sep):
            return os.path.relpath(candidate, training_dir)
        return candidate

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _timestamp(value) -> str | None:
        return value.isoformat() if value else None

    def _summary(self, row) -> dict:
        return {
            "id": row["id"],
            "title": row["title"],
            "objective": row["objective"],
            "componentName": row["component_name"],
            "componentType": row["component_type"],
            "confidence": self._optional_float(row["confidence"]),
            "status": row["status"],
            "userId": row.get("user_id"),
            "createdBy": row.get("created_by"),
            "stepCount": int(row["step_count"] or 0),
            "completedStepCount": int(row["completed_step_count"] or 0),
            "createdAt": self._timestamp(row["created_at"]),
            "updatedAt": self._timestamp(row["updated_at"]),
        }

    def _plan(self, row) -> dict:
        return {
            "id": row["id"],
            "title": row["title"],
            "objective": row["objective"],
            "componentName": row["component_name"],
            "componentType": row["component_type"],
            "summary": row["summary"] or "",
            "confidence": self._optional_float(row["confidence"]),
            "status": row["status"],
            "userId": row.get("user_id"),
            "createdBy": row["created_by"],
            "createdAt": self._timestamp(row["created_at"]),
            "updatedAt": self._timestamp(row["updated_at"]),
        }

    def _step(self, row) -> dict:
        return {
            "id": row["id"],
            "ordinal": int(row["ordinal"]),
            "type": row["step_type"],
            "title": row["title"],
            "instruction": row["instruction"],
            "note": row["note"] or "",
            "sourcePath": row["source_path"],
            "page": row["page_number"],
            "completed": bool(row["completed_at"]),
            "completedAt": self._timestamp(row["completed_at"]),
        }

    def _source(self, row) -> dict:
        return {
            "id": row["id"],
            "sourcePath": row["source_path"],
            "displayName": row["display_name"],
            "pages": list(row["pages"] or []),
            "chunkCount": int(row["chunk_count"] or 0),
        }

    def _note(self, row) -> dict:
        return {
            "id": row["id"],
            "role": row["role"],
            "message": row["message"],
            "createdAt": self._timestamp(row["created_at"]),
        }

    def _evidence_chunk(self, row) -> dict:
        return {
            "sourcePath": row["source_path"],
            "displayName": row["display_name"],
            "chunkIndex": int(row["chunk_index"]),
            "page": row["page_number"],
            "section": row["section_title"] or "Unknown",
            "category": row["category"] or "Uncategorized",
            "quality": self._optional_float(row["quality_score"]),
            "preview": (row["chunk_text"] or "")[:900],
        }

    def _evidence_image(self, row) -> dict:
        return {
            "sourcePath": row["source_path"],
            "displayName": row["display_name"],
            "imageKey": row["image_key"],
            "caption": row["caption"] or row["image_key"],
            "page": row["page_number"],
            "width": int(row["width_px"] or 0),
            "height": int(row["height_px"] or 0),
            "imageMimeType": row["image_mime_type"] or "image/png",
            "imageBase64": row["image_base64"],
        }

    def _learning(self, row) -> dict:
        return {
            "planId": row["plan_id"],
            "userId": int(row["user_id"]),
            "currentOrdinal": int(row["current_ordinal"]),
            "modeEnabled": bool(row["mode_enabled"]),
            "createdAt": self._timestamp(row["created_at"]),
            "updatedAt": self._timestamp(row["updated_at"]),
        }

    def _photo_check(self, row) -> dict:
        return {
            "id": row["id"],
            "planId": row["plan_id"],
            "userId": int(row["user_id"]),
            "imageMimeType": row["image_mime_type"],
            "note": row["note"] or "",
            "checklist": row["checklist"] or "",
            "diagnostics": dict(row["diagnostics"] or {}),
            "createdAt": self._timestamp(row["created_at"]),
        }
