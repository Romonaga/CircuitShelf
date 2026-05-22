from __future__ import annotations

import os
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
                conn.execute(load_query("assembly_plan_list.sql")).fetchone()
            return True
        except UndefinedTable:
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Assembly plan store is not available: {exc}")
            return False

    def create_from_card(self, *, question: str, card: dict[str, Any], created_by: str | None = None) -> dict:
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
                    created_by,
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
        return self.get(plan_id) or {}

    def list(self) -> list[dict]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("assembly_plan_list.sql")).fetchall()
        return [self._summary(row) for row in rows]

    def get(self, plan_id: str) -> dict | None:
        with self.database.connection() as conn:
            plan = conn.execute(load_query("assembly_plan_get.sql"), (plan_id,)).fetchone()
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

    def set_step_completed(self, plan_id: str, step_id: str, completed: bool) -> bool:
        with self.database.connection() as conn:
            row = conn.execute(load_query("assembly_step_completion_update.sql"), (bool(completed), step_id, plan_id)).fetchone()
            if row:
                conn.execute(load_query("assembly_plan_touch.sql"), (plan_id,))
        return bool(row)

    def add_note(self, plan_id: str, role: str, message: str) -> dict:
        with self.database.connection() as conn:
            row = conn.execute(load_query("assembly_note_insert.sql"), (plan_id, role, message)).fetchone()
            conn.execute(load_query("assembly_plan_touch.sql"), (plan_id,))
        return self._note(row)

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
