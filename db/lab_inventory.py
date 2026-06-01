from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from typing import Any

from psycopg.errors import UndefinedColumn, UndefinedTable

from db.connection import Database
from db.sql import load_query
from db.text import clean_db_text


GENERIC_PART_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\b(?:ne|lm)?555\b|\b555\s+timer\b", re.IGNORECASE), "NE555 timer", "timer"),
    (re.compile(r"\b4n35\b|\boptocoupler\b", re.IGNORECASE), "4N35 optocoupler", "optocoupler"),
    (re.compile(r"\bads1115\b|\banalog[-\s]?to[-\s]?digital\b|\badc\b", re.IGNORECASE), "ADS1115 ADC", "adc"),
    (re.compile(r"\barduino\b", re.IGNORECASE), "Arduino board", "board"),
    (re.compile(r"\braspberry\s*pi\b|\bgpio\b", re.IGNORECASE), "Raspberry Pi or GPIO board", "board"),
    (re.compile(r"\bbreadboard\b", re.IGNORECASE), "Breadboard", "tooling"),
    (re.compile(r"\bjumper\s+wires?\b|\bjumpers?\b", re.IGNORECASE), "Jumper wires", "tooling"),
    (re.compile(r"\bleds?\b|light emitting diode", re.IGNORECASE), "LED", "indicator"),
    (re.compile(r"\brelay\b", re.IGNORECASE), "Relay", "relay"),
    (re.compile(r"\bmosfet\b", re.IGNORECASE), "MOSFET", "transistor"),
    (re.compile(r"\btransistors?\b", re.IGNORECASE), "Transistor", "transistor"),
    (re.compile(r"\bop[\s-]?amp\b|\boperational amplifier\b", re.IGNORECASE), "Op amp", "op amp"),
    (re.compile(r"\bpower\s+supply\b|\bbattery\b", re.IGNORECASE), "Power supply", "power"),
)

RESISTOR_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:ohms?|[kKmM]?\s?ohms?|[kKmM]?Ω|kohm|megohm)s?\b")
CAPACITOR_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:pF|nF|uF|µF|mF|farads?)\b", re.IGNORECASE)


def normalize_part_name(value: str) -> str:
    text = str(value or "").replace("µ", "u").replace("Ω", "ohm").replace("ω", "ohm").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_part_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_part_name(value))


def part_lookup_keys(value: str, part_type: str = "") -> list[str]:
    text = normalize_part_name(value)
    compact = compact_part_key(value)
    keys = OrderedDict()
    for key in (text, compact):
        if key:
            keys.setdefault(key, key)

    combined = f"{text} {normalize_part_name(part_type)}"
    if re.search(r"\b(?:ne|lm)?555\b|\b555 timer\b", combined):
        for key in ("555", "555 timer", "ne555", "lm555", "ne555 timer", "lm555 timer"):
            keys.setdefault(key, key)
    if re.search(r"\bleds?\b|light emitting diode", combined):
        for key in ("led", "leds", "light emitting diode"):
            keys.setdefault(key, key)
    if re.search(r"\bpower supply\b|\bbattery\b", combined):
        for key in ("power supply", "battery", "bench supply"):
            keys.setdefault(key, key)
    if "breadboard" in combined:
        keys.setdefault("breadboard", "breadboard")
    if "jumper" in combined:
        keys.setdefault("jumper wires", "jumper wires")
        keys.setdefault("jumpers", "jumpers")

    return list(keys.values())


class LabInventoryStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("lab_parts_list.sql"), (-1,)).fetchall()
            return True
        except (UndefinedTable, UndefinedColumn):
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Lab inventory store is not available: {exc}")
            return False

    def list_parts(self, user_id: int) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("lab_parts_list.sql"), (user_id,)).fetchall()
        return [self._part_payload(row) for row in rows]

    def upsert_part(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        display_name = clean_db_text(payload.get("displayName") or payload.get("name") or "").strip()
        if not display_name:
            raise ValueError("Part name is required.")

        normalized = normalize_part_name(display_name)
        aliases = self._normalized_aliases(payload.get("aliases") or [])
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("lab_part_upsert.sql"),
                (
                    user_id,
                    display_name,
                    normalized,
                    clean_db_text(payload.get("partType") or payload.get("type") or "component"),
                    max(0, int(payload.get("quantity") or 0)),
                    clean_db_text(payload.get("location") or ""),
                    clean_db_text(payload.get("notes") or ""),
                ),
            ).fetchone()
            part_id = row["id"]
            conn.execute(load_query("lab_part_aliases_delete.sql"), (part_id,))
            for alias in aliases:
                conn.execute(load_query("lab_part_alias_insert.sql"), (part_id, alias, normalize_part_name(alias)))
            row = conn.execute(load_query("lab_part_get.sql"), (part_id, user_id)).fetchone()
        return self._part_payload(row)

    def delete_part(self, user_id: int, part_id: str) -> bool:
        with self.database.connection() as conn:
            row = conn.execute(load_query("lab_part_delete.sql"), (part_id, user_id)).fetchone()
        return bool(row)

    def inventory_terms(self, user_id: int) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("lab_inventory_terms.sql"), (user_id, user_id)).fetchall()
        return [dict(row) for row in rows]

    def _normalized_aliases(self, aliases: Any) -> list[str]:
        if isinstance(aliases, str):
            aliases = re.split(r"[,;\n]", aliases)
        result = OrderedDict()
        for alias in aliases or []:
            text = clean_db_text(alias or "").strip()
            normalized = normalize_part_name(text)
            if text and normalized:
                result.setdefault(normalized, text)
        return list(result.values())

    def _part_payload(self, row) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "userId": int(row["user_id"]),
            "displayName": row["display_name"],
            "normalizedName": row["normalized_name"],
            "partType": row["part_type"],
            "quantity": int(row["quantity"] or 0),
            "location": row["location"] or "",
            "notes": row["notes"] or "",
            "aliases": list(row["aliases"] or []),
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
        }


class ProjectFinderStore:
    def __init__(self, database: Database, inventory_store: LabInventoryStore, logger=None):
        self.database = database
        self.inventory_store = inventory_store
        self.logger = logger

    def find(self, user_id: int, *, limit: int = 24) -> dict[str, Any]:
        inventory = self.inventory_store.list_parts(user_id)
        term_rows = self.inventory_store.inventory_terms(user_id)
        terms = self._search_terms(term_rows)
        if not inventory or not terms:
            return {"inventoryCount": len(inventory), "candidates": []}

        with self.database.connection() as conn:
            chunk_rows = conn.execute(
                load_query("project_finder_chunk_candidates.sql"),
                (terms, min(max(limit * 6, 20), 200)),
            ).fetchall()
            intelligence_rows = conn.execute(
                load_query("project_finder_intelligence_candidates.sql"),
                (terms, min(max(limit, 10), 80)),
            ).fetchall()

        inventory_index = self._inventory_index(inventory, term_rows)
        candidates = [
            self._chunk_candidate(row, inventory_index)
            for row in chunk_rows
        ]
        candidates.extend(self._intelligence_candidate(row, inventory_index) for row in intelligence_rows)
        ranked = sorted(
            self._dedupe_candidates(candidates),
            key=lambda item: (item["buildable"], item["score"], item["matchedPartCount"]),
            reverse=True,
        )
        return {
            "inventoryCount": len(inventory),
            "termCount": len(terms),
            "buildableCount": sum(1 for candidate in ranked if candidate["buildable"]),
            "needsPartsCount": sum(1 for candidate in ranked if not candidate["buildable"]),
            "missingPartSummary": self._missing_part_summary(ranked),
            "candidates": ranked[:limit],
        }

    def _search_terms(self, rows: list[dict[str, Any]]) -> list[str]:
        terms = OrderedDict()
        for row in rows:
            term = normalize_part_name(row.get("term") or row.get("normalized_term") or "")
            if len(term) >= 2:
                terms.setdefault(term, term)
        return list(terms.values())[:300]

    def _inventory_index(self, inventory: list[dict[str, Any]], term_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for part in inventory:
            for key in part_lookup_keys(part["displayName"], part.get("partType") or ""):
                index[key] = part
            for key in part_lookup_keys(part.get("partType") or "", part.get("partType") or ""):
                index[key] = part
            for alias in part.get("aliases") or []:
                for key in part_lookup_keys(alias, part.get("partType") or ""):
                    index[key] = part
        for row in term_rows:
            part = {
                "id": str(row["part_id"]),
                "displayName": row["display_name"],
                "normalizedName": row["normalized_name"],
                "partType": row["part_type"],
                "quantity": int(row["quantity"] or 0),
                "location": row["location"] or "",
                "notes": row["notes"] or "",
            }
            for key in part_lookup_keys(row.get("term") or row.get("normalized_term") or "", row.get("part_type") or ""):
                index[key] = part
            for key in part_lookup_keys(row.get("normalized_term") or "", row.get("part_type") or ""):
                index[key] = part
            for key in part_lookup_keys(row.get("part_type") or "", row.get("part_type") or ""):
                index[key] = part
        return {key: value for key, value in index.items() if key}

    def _chunk_candidate(self, row, inventory_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
        text = row["chunk_text"] or ""
        matched = self._matched_parts(row["matched_terms"] or [], inventory_index)
        required = infer_required_parts(text)
        missing = self._missing_parts(required, inventory_index)
        score = int(row["matched_count"] or 0) * 18 + float(row["quality_score"] or 0.0) * 10 - len(missing) * 4
        project_like = self._is_project_like(text, required, matched)
        if project_like:
            score += 10
        title = self._candidate_title(row["display_name"], row["section_title"], required, matched)
        return {
            "id": self._candidate_id("chunk", row["source_path"], row["chunk_index"]),
            "kind": "project_chunk",
            "title": title,
            "objective": f"Build or explore: {title}",
            "summary": self._preview(text),
            "source": row["source_path"],
            "displayName": row["display_name"],
            "page": row["page_number"],
            "chunkIndex": int(row["chunk_index"]),
            "matchedParts": matched,
            "matchedPartCount": len(matched),
            "requiredParts": required,
            "missingParts": missing,
            "suggestedSubstitutions": [],
            "buildable": len(missing) == 0 and len(matched) > 0,
            "projectLike": project_like,
            "score": round(score, 2),
        }

    def _intelligence_candidate(self, row, inventory_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
        matched = self._matched_parts(row["matched_terms"] or [], inventory_index)
        component = row["component_name"] or row["display_name"]
        required = _dedupe_parts([{"name": component, "type": row["component_type"] or "component"}])
        return {
            "id": self._candidate_id("intel", row["source_path"], component),
            "kind": "component_reference",
            "title": f"{component} reference project starter",
            "objective": f"Create a simple beginner project using {component}.",
            "summary": row["summary"] or f"{component} appears in your indexed sources and matches your inventory.",
            "source": row["source_path"],
            "displayName": row["display_name"],
            "page": None,
            "chunkIndex": None,
            "matchedParts": matched,
            "matchedPartCount": len(matched),
            "requiredParts": required,
            "missingParts": [],
            "suggestedSubstitutions": [],
            "buildable": len(matched) > 0,
            "projectLike": True,
            "score": round(14 + len(matched) * 20 + float(row["confidence"] or 0.0) * 15, 2),
        }

    def _matched_parts(self, terms: list[str], inventory_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        result = OrderedDict()
        for term in terms:
            part = self._find_inventory_part(term, "", inventory_index)
            if part:
                result.setdefault(part["id"], {
                    "id": part["id"],
                    "displayName": part["displayName"],
                    "partType": part.get("partType") or part.get("part_type") or "component",
                    "quantity": int(part.get("quantity") or 0),
                    "location": part.get("location") or "",
                })
        return list(result.values())

    def _missing_parts(self, required_parts: list[dict[str, str]], inventory_index: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
        missing = []
        for part in required_parts:
            if self._find_inventory_part(part["name"], part.get("type") or "", inventory_index):
                continue
            if part["type"] in {"resistor", "capacitor"} and part["type"] in inventory_index:
                continue
            missing.append(part)
        return missing[:8]

    def _find_inventory_part(
        self,
        name: str,
        part_type: str,
        inventory_index: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        for key in part_lookup_keys(name, part_type):
            if key in inventory_index:
                return inventory_index[key]
        return None

    def _is_project_like(self, text: str, required: list[dict[str, str]], matched: list[dict[str, Any]]) -> bool:
        if re.search(
            r"\b(project|experiment|build|breadboard|wire|connect|schematic|circuit|diagram|parts?|component|pin)\b",
            text or "",
            re.IGNORECASE,
        ):
            return True
        return len(required) >= 2 and len(matched) > 0

    def _candidate_title(
        self,
        display_name: str,
        section_title: str | None,
        required: list[dict[str, str]],
        matched: list[dict[str, Any]],
    ) -> str:
        if section_title and section_title.lower() not in {"unknown", "untitled section"}:
            return str(section_title)[:90]
        if required:
            return f"{required[0]['name']} circuit from {display_name}"
        if matched:
            return f"{matched[0]['displayName']} project from {display_name}"
        return f"Project candidate from {display_name}"

    def _preview(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        return cleaned[:520]

    def _dedupe_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = OrderedDict()
        for candidate in candidates:
            if not candidate.get("projectLike"):
                continue
            key = self._candidate_dedupe_key(candidate)
            existing = result.get(key)
            if not existing or candidate["score"] > existing["score"]:
                result[key] = candidate
        return list(result.values())

    def _candidate_dedupe_key(self, candidate: dict[str, Any]) -> str:
        required = sorted(
            normalize_part_name(part.get("name") or part.get("displayName") or "")
            for part in candidate.get("requiredParts") or []
        )
        if required:
            signature = "|".join(required)
        else:
            signature = normalize_part_name(candidate.get("title") or candidate.get("summary") or "")
        return "|".join(
            [
                str(candidate.get("kind") or ""),
                str(candidate.get("source") or ""),
                normalize_part_name(candidate.get("title") or ""),
                signature,
            ]
        )

    def _missing_part_summary(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        summary: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for candidate in candidates:
            for part in candidate.get("missingParts") or []:
                key = normalize_part_name(part.get("name") or part.get("displayName") or "")
                if not key:
                    continue
                item = summary.setdefault(
                    key,
                    {
                        "name": part.get("name") or part.get("displayName") or "Unknown part",
                        "type": part.get("type") or part.get("partType") or "component",
                        "count": 0,
                        "exampleTitles": [],
                    },
                )
                item["count"] += 1
                if len(item["exampleTitles"]) < 3 and candidate.get("title"):
                    item["exampleTitles"].append(candidate["title"])
        return sorted(summary.values(), key=lambda item: item["count"], reverse=True)[:10]

    def _candidate_id(self, *parts: Any) -> str:
        digest = hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
        return digest[:16]


def infer_required_parts(text: str) -> list[dict[str, str]]:
    required: list[dict[str, str]] = []
    for pattern, name, part_type in GENERIC_PART_PATTERNS:
        if pattern.search(text or ""):
            required.append({"name": name, "type": part_type})

    for value in RESISTOR_RE.findall(text or "")[:8]:
        required.append({"name": normalize_part_value(value, "resistor"), "type": "resistor"})
    for value in CAPACITOR_RE.findall(text or "")[:8]:
        required.append({"name": normalize_part_value(value, "capacitor"), "type": "capacitor"})
    return _dedupe_parts(required)


def normalize_part_value(value: str, fallback: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("Ω", " ohm").strip())
    if not text:
        return fallback
    return text if fallback.lower() in text.lower() else f"{text} {fallback}"


def _dedupe_parts(parts: list[dict[str, str]]) -> list[dict[str, str]]:
    result = OrderedDict()
    for part in parts:
        name = clean_db_text(part.get("name") or "").strip()
        part_type = clean_db_text(part.get("type") or "component").strip()
        normalized = normalize_part_name(name)
        if name and normalized:
            result.setdefault(normalized, {"name": name, "type": part_type})
    return list(result.values())
