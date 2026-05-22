from __future__ import annotations

from typing import Any

from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query


class ConversationStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("conversation_list.sql"), (None, None, 1)).fetchone()
            return True
        except UndefinedTable:
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Conversation store is not available: {exc}")
            return False

    def list(self, user_id: int | None, *, limit: int = 50) -> list[dict]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("conversation_list.sql"), (user_id, user_id, int(limit))).fetchall()
        return [self._summary(row) for row in rows]

    def create(self, user_id: int, title: str) -> dict:
        with self.database.connection() as conn:
            row = conn.execute(load_query("conversation_insert.sql"), (user_id, self._clean_title(title), user_id)).fetchone()
        if not row:
            raise ValueError("User not found.")
        return self._summary(row)

    def get(self, conversation_id: str, user_id: int | None) -> dict | None:
        with self.database.connection() as conn:
            row = conn.execute(load_query("conversation_get.sql"), (conversation_id, user_id, user_id)).fetchone()
            if not row:
                return None
            turns = conn.execute(load_query("conversation_turns_get.sql"), (conversation_id,)).fetchall()
        return {
            **self._summary(row),
            "turns": [self._turn(turn) for turn in turns],
        }

    def append_turn(
        self,
        *,
        conversation_id: str,
        question: str,
        answer: str,
        model_name: str,
        retrieval_strategy: str,
        confidence_score: Any,
    ) -> dict:
        with self.database.connection() as conn:
            turn = conn.execute(
                load_query("conversation_turn_insert.sql"),
                (
                    conversation_id,
                    conversation_id,
                    question,
                    answer,
                    model_name,
                    retrieval_strategy,
                    self._optional_float(confidence_score),
                ),
            ).fetchone()
            conn.execute(load_query("conversation_touch.sql"), (conversation_id,))
        return self._turn(turn)

    def update_title(self, conversation_id: str, title: str) -> None:
        with self.database.connection() as conn:
            conn.execute(load_query("conversation_title_update.sql"), (self._clean_title(title), conversation_id))

    def archive(self, conversation_id: str, user_id: int | None) -> bool:
        with self.database.connection() as conn:
            row = conn.execute(load_query("conversation_archive.sql"), (conversation_id, user_id, user_id)).fetchone()
        return bool(row)

    @staticmethod
    def _clean_title(title: str) -> str:
        cleaned = " ".join(str(title or "").split())
        if not cleaned:
            return "New conversation"
        return cleaned[:80]

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _timestamp(value) -> str | None:
        return value.isoformat() if value else None

    def _summary(self, row) -> dict:
        return {
            "id": str(row["id"]),
            "userId": row.get("user_id"),
            "username": row.get("username"),
            "title": row["title"],
            "turnCount": int(row.get("turn_count") or 0),
            "createdAt": self._timestamp(row.get("created_at")),
            "updatedAt": self._timestamp(row.get("updated_at")),
            "lastTurnAt": self._timestamp(row.get("last_turn_at")),
        }

    def _turn(self, row) -> dict:
        return {
            "id": str(row["id"]),
            "ordinal": int(row["ordinal"]),
            "question": row["question"],
            "answer": row["answer_markdown"],
            "modelName": row.get("model_name"),
            "retrievalStrategy": row.get("retrieval_strategy"),
            "confidence": self._optional_float(row.get("confidence_score")),
            "createdAt": self._timestamp(row.get("created_at")),
        }
