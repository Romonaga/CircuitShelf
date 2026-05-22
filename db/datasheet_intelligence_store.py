from __future__ import annotations

from psycopg.errors import UndefinedColumn, UndefinedTable

from db.connection import Database
from db.sql import load_query


class DatasheetIntelligenceStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            self.get_for_source("__missing__")
            return True
        except (UndefinedTable, UndefinedColumn):
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Datasheet intelligence store is not available: {exc}")
            return False

    def replace_for_source(self, source_path: str, intelligence: dict) -> dict | None:
        with self.database.connection() as conn:
            conn.execute(load_query("datasheet_intelligence_delete.sql"), (source_path,))
            row = conn.execute(
                load_query("datasheet_intelligence_summary_upsert.sql"),
                (
                    intelligence.get("componentName") or "",
                    intelligence.get("componentType") or "component",
                    intelligence.get("summary") or "",
                    float(intelligence.get("confidence") or 0.0),
                    source_path,
                ),
            ).fetchone()
            if not row:
                return None
            intelligence_id = row["id"]
            for fact in intelligence.get("facts") or []:
                conn.execute(
                    load_query("datasheet_intelligence_fact_insert.sql"),
                    (
                        intelligence_id,
                        fact.get("type") or "note",
                        fact.get("label") or "",
                        fact.get("value") or "",
                        fact.get("unit") or "",
                        fact.get("page"),
                        fact.get("chunkIndex"),
                        fact.get("evidence") or "",
                        float(fact.get("confidence") or 0.0),
                    ),
                )
            for pin in (intelligence.get("pinout") or {}).get("pins") or []:
                conn.execute(
                    load_query("datasheet_intelligence_pin_insert.sql"),
                    (
                        intelligence_id,
                        int(pin.get("pin")),
                        pin.get("label") or "",
                        pin.get("function") or "",
                        pin.get("page"),
                        pin.get("chunkIndex"),
                        pin.get("evidence") or "",
                    ),
                )
        return self.get_for_source(source_path)

    def get_for_source(self, source_path: str) -> dict | None:
        with self.database.connection() as conn:
            summary = conn.execute(load_query("datasheet_intelligence_summary_get.sql"), (source_path,)).fetchone()
            if not summary:
                return None
            facts = conn.execute(load_query("datasheet_intelligence_facts_get.sql"), (summary["id"],)).fetchall()
            pins = conn.execute(load_query("datasheet_intelligence_pins_get.sql"), (summary["id"],)).fetchall()

        return {
            "source": summary["source_path"],
            "displayName": summary["display_name"],
            "componentName": summary["component_name"] or "",
            "componentType": summary["component_type"] or "component",
            "summary": summary["summary"] or "",
            "confidence": float(summary["confidence"] or 0.0),
            "updatedAt": summary["updated_at"].isoformat() if summary["updated_at"] else None,
            "facts": [
                {
                    "type": row["fact_type"],
                    "label": row["label"],
                    "value": row["value"],
                    "unit": row["unit"] or "",
                    "page": row["page_number"],
                    "chunkIndex": row["source_chunk_index"],
                    "evidence": row["evidence"] or "",
                    "confidence": float(row["confidence"] or 0.0),
                }
                for row in facts
            ],
            "pinout": {
                "source": summary["source_path"],
                "displayName": summary["display_name"],
                "pins": [
                    {
                        "pin": int(row["pin_number"]),
                        "label": row["label"],
                        "function": row["function_text"],
                        "page": row["page_number"],
                        "chunkIndex": row["source_chunk_index"],
                        "evidence": row["evidence"] or "",
                    }
                    for row in pins
                ],
            },
        }
