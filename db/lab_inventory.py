from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from typing import Any

from psycopg.errors import UndefinedColumn, UndefinedTable

from db.connection import Database
from db.sql import load_query
from db.text import clean_db_text


LOW_VALUE_TITLE_RE = re.compile(
    r"\b(?:image\s+ocr|figure|fig\.?|table|parts?\s+for\s+fig|untitled|unknown)\b",
    re.IGNORECASE,
)
LOW_VALUE_TEXT_RE = re.compile(
    r"\b(?:copyright|all\s+rights\s+reserved|editorial|publisher|isbn|website|email)\b",
    re.IGNORECASE,
)
BUILD_ACTION_RE = re.compile(
    r"\b(?:build|make|construct|assemble|breadboard|wire|connect|solder|test|try|experiment|project)\b",
    re.IGNORECASE,
)
CIRCUIT_CONTEXT_RE = re.compile(
    r"\b(?:circuit|schematic|diagram|parts?\s+list|component|pin|resistor|capacitor|transistor|timer|led|arduino|raspberry\s*pi|gpio)\b",
    re.IGNORECASE,
)
CODE_SAMPLE_TITLE_RE = re.compile(r"\bcode\s+sample\b", re.IGNORECASE)
MIN_PROJECT_TEXT_CHARS = 90
PROJECT_FINDER_CHUNK_SOURCE_LIMIT = 5000
PROJECT_FINDER_INTELLIGENCE_SOURCE_LIMIT = 400

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

    def list_locations(self, user_id: int) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("lab_locations_list.sql"), (user_id,)).fetchall()
        return [self._location_payload(row) for row in rows]

    def upsert_location(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        display_name = clean_db_text(payload.get("displayName") or payload.get("name") or "").strip()
        if not display_name:
            raise ValueError("Location name is required.")
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("lab_location_upsert.sql"),
                (
                    int(user_id),
                    display_name,
                    normalize_part_name(display_name),
                    clean_db_text(payload.get("notes") or ""),
                ),
            ).fetchone()
        return self._location_payload(row)

    def upsert_part(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        display_name = clean_db_text(payload.get("displayName") or payload.get("name") or "").strip()
        if not display_name:
            raise ValueError("Part name is required.")

        normalized = normalize_part_name(display_name)
        aliases = self._normalized_aliases(payload.get("aliases") or [])
        part_id = str(payload.get("id") or "").strip()
        with self.database.connection() as conn:
            location_id, location_label = self._resolve_location(conn, user_id, payload)
            values = (
                display_name,
                normalized,
                clean_db_text(payload.get("partType") or payload.get("type") or "component"),
                max(0, int(payload.get("quantity") or 0)),
                location_id,
                location_label,
                clean_db_text(payload.get("notes") or ""),
            )
            if part_id:
                row = conn.execute(load_query("lab_part_update.sql"), (*values, part_id, user_id)).fetchone()
                if not row:
                    raise ValueError("Inventory part not found.")
            else:
                row = conn.execute(
                    load_query("lab_part_upsert.sql"),
                    (
                        user_id,
                        *values,
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

    def _resolve_location(self, conn, user_id: int, payload: dict[str, Any]) -> tuple[str | None, str]:
        location_id = str(payload.get("locationId") or "").strip()
        if location_id:
            row = conn.execute(load_query("lab_location_get.sql"), (location_id, int(user_id))).fetchone()
            if not row:
                raise ValueError("Inventory location not found.")
            return str(row["id"]), row["display_name"] or ""

        location_name = clean_db_text(payload.get("location") or "").strip()
        if not location_name:
            return None, ""
        row = conn.execute(
            load_query("lab_location_upsert.sql"),
            (
                int(user_id),
                location_name,
                normalize_part_name(location_name),
                "",
            ),
        ).fetchone()
        return str(row["id"]), row["display_name"] or location_name

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
            "locationId": str(row["location_id"]) if row.get("location_id") else None,
            "location": row["location"] or "",
            "notes": row["notes"] or "",
            "aliases": list(row["aliases"] or []),
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    @staticmethod
    def _location_payload(row) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "userId": int(row["user_id"]),
            "displayName": row["display_name"],
            "normalizedName": row["normalized_name"],
            "notes": row["notes"] or "",
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
        }


class ProjectFinderStore:
    def __init__(self, database: Database, inventory_store: LabInventoryStore, logger=None, ai_triage_service=None):
        self.database = database
        self.inventory_store = inventory_store
        self.logger = logger
        self.ai_triage_service = ai_triage_service

    def find(
        self,
        user_id: int,
        *,
        limit: int = 24,
        offset: int = 0,
        candidate_filter: str = "all",
        entity_id: int | None = None,
    ) -> dict[str, Any]:
        limit = max(1, int(limit))
        offset = max(0, int(offset))
        inventory = self.inventory_store.list_parts(user_id)
        term_rows = self.inventory_store.inventory_terms(user_id)
        terms = self._search_terms(term_rows)
        if not inventory or not terms:
            return self._finder_response(
                inventory_count=len(inventory),
                term_count=len(terms),
                ranked=[],
                limit=limit,
                offset=offset,
                candidate_filter=candidate_filter,
            )
            return self._maybe_triage_response(response, entity_id=entity_id, user_id=user_id)

        with self.database.connection() as conn:
            chunk_rows = conn.execute(
                load_query("project_finder_chunk_candidates.sql"),
                (self._term_regex(terms), PROJECT_FINDER_CHUNK_SOURCE_LIMIT),
            ).fetchall()
            intelligence_rows = conn.execute(
                load_query("project_finder_intelligence_candidates.sql"),
                (terms, PROJECT_FINDER_INTELLIGENCE_SOURCE_LIMIT),
            ).fetchall()

        inventory_index = self._inventory_index(inventory, term_rows)
        chunk_rows = self._annotate_chunk_matches(chunk_rows, self._prepared_search_terms(terms))
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
        response = self._finder_response(
            inventory_count=len(inventory),
            term_count=len(terms),
            ranked=ranked,
            limit=limit,
            offset=offset,
            candidate_filter=candidate_filter,
        )
        return self._maybe_triage_response(response, entity_id=entity_id, user_id=user_id)

    def _maybe_triage_response(
        self,
        response: dict[str, Any],
        *,
        entity_id: int | None,
        user_id: int | None,
    ) -> dict[str, Any]:
        if not self.ai_triage_service:
            return response
        return self.ai_triage_service.triage_response(response, entity_id=entity_id, user_id=user_id)

    def _finder_response(
        self,
        *,
        inventory_count: int,
        term_count: int,
        ranked: list[dict[str, Any]],
        limit: int,
        offset: int,
        candidate_filter: str,
    ) -> dict[str, Any]:
        normalized_filter = self._normalize_candidate_filter(candidate_filter)
        filtered = self._filter_candidates(ranked, normalized_filter)
        page = filtered[offset:offset + limit]
        return {
            "inventoryCount": inventory_count,
            "termCount": term_count,
            "candidateCount": len(ranked),
            "buildableCount": sum(1 for candidate in ranked if candidate["buildable"]),
            "needsPartsCount": sum(1 for candidate in ranked if not candidate["buildable"]),
            "missingPartSummary": self._missing_part_summary(ranked),
            "filter": normalized_filter,
            "filterCount": len(filtered),
            "offset": offset,
            "limit": limit,
            "returnedCount": len(page),
            "hasMore": offset + len(page) < len(filtered),
            "candidates": page,
        }

    @staticmethod
    def _normalize_candidate_filter(candidate_filter: str) -> str:
        if candidate_filter in {"buildable", "needs-parts"}:
            return candidate_filter
        return "all"

    @staticmethod
    def _filter_candidates(ranked: list[dict[str, Any]], candidate_filter: str) -> list[dict[str, Any]]:
        if candidate_filter == "buildable":
            return [candidate for candidate in ranked if candidate["buildable"]]
        if candidate_filter == "needs-parts":
            return [candidate for candidate in ranked if not candidate["buildable"]]
        return ranked

    def _search_terms(self, rows: list[dict[str, Any]]) -> list[str]:
        terms = OrderedDict()
        for row in rows:
            term = normalize_part_name(row.get("term") or row.get("normalized_term") or "")
            if len(term) >= 2:
                terms.setdefault(term, term)
        return list(terms.values())[:300]

    def _term_regex(self, terms: list[str]) -> str:
        patterns = []
        for term in terms:
            words = re.findall(r"[a-z0-9]+", normalize_part_name(term))
            if not words:
                continue
            pattern = r"[^[:alnum:]]+".join(re.escape(word) for word in words)
            if len(pattern) >= 2:
                patterns.append(pattern)
        if not patterns:
            return r"a^"
        deduped = sorted(set(patterns), key=lambda value: (-len(value), value))
        return r"(^|[^[:alnum:]])(" + "|".join(deduped) + r")([^[:alnum:]]|$)"

    def _prepared_search_terms(self, terms: list[str]) -> list[tuple[str, str]]:
        prepared = OrderedDict()
        for term in terms:
            normalized = normalize_part_name(term)
            if not normalized:
                continue
            prepared.setdefault(normalized, (normalized, compact_part_key(normalized)))
        return list(prepared.values())

    def _annotate_chunk_matches(self, rows: list[dict[str, Any]], terms: list[tuple[str, str]]) -> list[dict[str, Any]]:
        annotated = []
        for row in rows:
            payload = dict(row)
            matched_terms = self._matched_terms_for_text(payload.get("chunk_text") or "", terms)
            if not matched_terms:
                continue
            payload["matched_terms"] = matched_terms
            payload["matched_count"] = len(matched_terms)
            annotated.append(payload)
        return annotated

    def _matched_terms_for_text(self, text: str, terms: list[tuple[str, str]]) -> list[str]:
        normalized_text = normalize_part_name(text)
        compact_text = compact_part_key(text)
        matched = []
        for normalized_term, compact_term in terms:
            if normalized_term in normalized_text or (compact_term and compact_term in compact_text):
                matched.append(normalized_term)
        return matched

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
        required_resolution = self._resolve_required_parts(required, inventory_index)
        matched = self._merge_matched_parts(matched, required_resolution["matchedParts"])
        missing = required_resolution["missingParts"]
        score = int(row["matched_count"] or 0) * 18 + float(row["quality_score"] or 0.0) * 10 - len(missing) * 4
        project_like, rejection_reasons = self._project_qualification(text, row["section_title"], required, matched)
        if project_like:
            score += 10
        title = self._candidate_title(row["display_name"], row["section_title"], required, matched)
        if rejection_reasons:
            score -= len(rejection_reasons) * 8
        objective = self._candidate_objective(
            title=title,
            summary=self._preview(text),
            source=row["source_path"],
            page=row["page_number"],
            matched=matched,
            missing=missing,
            substitutions=required_resolution["suggestedSubstitutions"],
            rejection_reasons=rejection_reasons,
        )
        return {
            "id": self._candidate_id("chunk", row["source_path"], row["chunk_index"]),
            "kind": "project_chunk",
            "title": title,
            "objective": objective,
            "summary": self._preview(text),
            "source": row["source_path"],
            "displayName": row["display_name"],
            "page": row["page_number"],
            "chunkIndex": int(row["chunk_index"]),
            "matchedParts": matched,
            "matchedPartCount": len(matched),
            "requiredParts": required,
            "missingParts": missing,
            "suggestedSubstitutions": required_resolution["suggestedSubstitutions"],
            "matchReasons": required_resolution["matchReasons"],
            "missingReasons": required_resolution["missingReasons"],
            "rejectionReasons": rejection_reasons,
            "buildable": len(missing) == 0 and len(matched) > 0,
            "projectLike": project_like,
            "score": round(score, 2),
        }

    def _intelligence_candidate(self, row, inventory_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
        matched = self._matched_parts(row["matched_terms"] or [], inventory_index)
        component = row["component_name"] or row["display_name"]
        required = _dedupe_parts([{"name": component, "type": row["component_type"] or "component"}])
        required_resolution = self._resolve_required_parts(required, inventory_index)
        matched = self._merge_matched_parts(matched, required_resolution["matchedParts"])
        missing = required_resolution["missingParts"]
        title = f"{component} reference project starter"
        return {
            "id": self._candidate_id("intel", row["source_path"], component),
            "kind": "component_reference",
            "title": title,
            "objective": self._candidate_objective(
                title=title,
                summary=row["summary"] or f"{component} appears in indexed sources.",
                source=row["source_path"],
                page=None,
                matched=matched,
                missing=missing,
                substitutions=required_resolution["suggestedSubstitutions"],
                rejection_reasons=[],
            ),
            "summary": row["summary"] or f"{component} appears in your indexed sources and matches your inventory.",
            "source": row["source_path"],
            "displayName": row["display_name"],
            "page": None,
            "chunkIndex": None,
            "matchedParts": matched,
            "matchedPartCount": len(matched),
            "requiredParts": required,
            "missingParts": missing,
            "suggestedSubstitutions": required_resolution["suggestedSubstitutions"],
            "matchReasons": required_resolution["matchReasons"],
            "missingReasons": required_resolution["missingReasons"],
            "rejectionReasons": [],
            "buildable": len(missing) == 0 and len(matched) > 0,
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
        return self._resolve_required_parts(required_parts, inventory_index)["missingParts"]

    def _resolve_required_parts(
        self,
        required_parts: list[dict[str, str]],
        inventory_index: dict[str, dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        matched: OrderedDict[str, dict[str, Any]] = OrderedDict()
        missing: list[dict[str, Any]] = []
        substitutions: list[dict[str, str]] = []
        match_reasons: list[str] = []
        missing_reasons: list[str] = []
        for part in required_parts:
            name = part.get("name") or ""
            part_type = part.get("type") or "component"
            found = self._find_inventory_part(name, part_type, inventory_index)
            if found:
                part_id = str(found["id"])
                matched.setdefault(
                    part_id,
                    {
                        "id": part_id,
                        "displayName": found["displayName"],
                        "partType": found.get("partType") or found.get("part_type") or part_type,
                        "quantity": int(found.get("quantity") or 0),
                        "location": found.get("location") or "",
                    },
                )
                if normalize_part_name(name) != normalize_part_name(found["displayName"]):
                    substitutions.append(
                        {
                            "required": name,
                            "use": found["displayName"],
                            "reason": f"{found['displayName']} matches {name} through inventory aliases or family normalization.",
                        }
                    )
                match_reasons.append(f"{name} satisfied by {found['displayName']}.")
                continue
            if part_type in {"resistor", "capacitor"} and part_type in inventory_index:
                found = inventory_index[part_type]
                matched.setdefault(
                    str(found["id"]),
                    {
                        "id": str(found["id"]),
                        "displayName": found["displayName"],
                        "partType": found.get("partType") or found.get("part_type") or part_type,
                        "quantity": int(found.get("quantity") or 0),
                        "location": found.get("location") or "",
                    },
                )
                substitutions.append(
                    {
                        "required": name,
                        "use": found["displayName"],
                        "reason": f"Inventory has generic {part_type} stock; verify the exact value before building.",
                    }
                )
                match_reasons.append(f"{name} may be covered by generic {part_type} inventory.")
                continue
            reason = self._missing_reason(name, part_type)
            missing.append({"name": name, "type": part_type, "reason": reason})
            missing_reasons.append(reason)
        return {
            "matchedParts": list(matched.values()),
            "missingParts": missing[:8],
            "suggestedSubstitutions": substitutions[:8],
            "matchReasons": _dedupe_strings(match_reasons)[:8],
            "missingReasons": _dedupe_strings(missing_reasons)[:8],
        }

    def _merge_matched_parts(self, primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for part in [*primary, *secondary]:
            part_id = str(part.get("id") or part.get("displayName") or part.get("name") or "")
            if part_id:
                result.setdefault(part_id, part)
        return list(result.values())

    def _missing_reason(self, name: str, part_type: str) -> str:
        if part_type == "power" and not re.search(r"\b\d+(?:\.\d+)?\s*v\b|\b\d+(?:\.\d+)?\s*(?:ma|a)\b", name, re.IGNORECASE):
            return f"{name} is underspecified; source evidence needs voltage/current before selecting a supply."
        return f"{name} was not found in inventory aliases, part names, or normalized part families."

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
        return self._project_qualification(text, None, required, matched)[0]

    def _project_qualification(
        self,
        text: str,
        section_title: str | None,
        required: list[dict[str, str]],
        matched: list[dict[str, Any]],
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        title = section_title or ""
        if len(cleaned) < MIN_PROJECT_TEXT_CHARS:
            reasons.append("Evidence is too short to describe a buildable project.")
        if LOW_VALUE_TITLE_RE.search(title) and not BUILD_ACTION_RE.search(cleaned):
            reasons.append("Section title looks like OCR/table/figure noise rather than a project.")
        if LOW_VALUE_TEXT_RE.search(cleaned[:260]) and not BUILD_ACTION_RE.search(cleaned):
            reasons.append("Evidence is mostly publication or boilerplate text.")
        action = bool(BUILD_ACTION_RE.search(cleaned))
        context = bool(CIRCUIT_CONTEXT_RE.search(cleaned))
        enough_parts = len(required) >= 2 or (len(required) >= 1 and len(matched) >= 2)
        code_sample = bool(CODE_SAMPLE_TITLE_RE.search(title) or re.search(r"\b(setup|loop|pinmode|digitalwrite|analogread|#include|import\s+board)\b", cleaned, re.IGNORECASE))
        if code_sample and context and (required or matched):
            action = True
        project_like = action and context and (enough_parts or len(matched) > 0)
        if not project_like and not reasons:
            reasons.append("No clear build action, circuit context, and parts evidence were found together.")
        return project_like, _dedupe_strings(reasons)

    def _candidate_title(
        self,
        display_name: str,
        section_title: str | None,
        required: list[dict[str, str]],
        matched: list[dict[str, Any]],
    ) -> str:
        if (
            section_title
            and section_title.lower() not in {"unknown", "untitled section"}
            and not LOW_VALUE_TITLE_RE.search(section_title)
        ):
            return str(section_title)[:90]
        if required:
            return f"{required[0]['name']} circuit from {display_name}"
        if matched:
            return f"{matched[0]['displayName']} project from {display_name}"
        return f"Project candidate from {display_name}"

    def _candidate_objective(
        self,
        *,
        title: str,
        summary: str,
        source: str,
        page: int | None,
        matched: list[dict[str, Any]],
        missing: list[dict[str, Any]],
        substitutions: list[dict[str, str]],
        rejection_reasons: list[str],
    ) -> str:
        lines = [
            f"Create a Bench assembly plan from this Project Finder candidate: {title}.",
            f"Source: {source}" + (f", page {page}." if page else "."),
            f"Evidence summary: {summary}",
        ]
        if matched:
            lines.append("Inventory matches: " + ", ".join(part.get("displayName") or part.get("name") or "" for part in matched if part))
        if substitutions:
            lines.append(
                "Allowed substitutions or alias matches: "
                + "; ".join(f"{item['required']} -> {item['use']} ({item['reason']})" for item in substitutions)
            )
        if missing:
            lines.append("Unresolved or underspecified parts: " + "; ".join(part.get("reason") or part.get("name") or "" for part in missing))
        if rejection_reasons:
            lines.append("Candidate caveats: " + "; ".join(rejection_reasons))
        lines.append("Use only cited source evidence. If wiring or required values are missing, say what is missing instead of inventing it.")
        return "\n".join(lines)

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
                if existing:
                    candidate["dedupeCount"] = int(existing.get("dedupeCount") or 1) + 1
                result[key] = candidate
            elif existing:
                existing["dedupeCount"] = int(existing.get("dedupeCount") or 1) + 1
        return list(result.values())

    def _candidate_dedupe_key(self, candidate: dict[str, Any]) -> str:
        required = sorted(
            normalize_part_name(part.get("name") or part.get("displayName") or "")
            for part in candidate.get("requiredParts") or []
        )
        title = normalize_part_name(candidate.get("title") or "")
        if LOW_VALUE_TITLE_RE.search(title):
            title = ""
        if required:
            signature = "|".join(required)
        else:
            signature = normalize_part_name(candidate.get("title") or candidate.get("summary") or "")
        return "|".join(
            [
                str(candidate.get("kind") or ""),
                str(candidate.get("source") or ""),
                title,
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


def _dedupe_strings(values: list[str]) -> list[str]:
    result = OrderedDict()
    for value in values:
        text = clean_db_text(value or "").strip()
        if text:
            result.setdefault(text.lower(), text)
    return list(result.values())
