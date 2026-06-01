from __future__ import annotations

from typing import Any

from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query


class RuntimeConfigStore:
    """Structured runtime config backed by relational tables."""

    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def seed_from_config(self, config: dict[str, Any]) -> dict[str, int]:
        if not self.database.configured:
            return {}

        seeded = {
            "llm_models": 0,
            "query_synonyms": 0,
            "prompt_security_banned_phrases": 0,
            "rerank_profiles": 0,
            "chunk_categories": 0,
            "equation_patterns": 0,
        }
        try:
            with self.database.connection() as conn:
                if self._count(conn, "runtime_llm_models_count.sql") == 0:
                    seeded["llm_models"] = self._seed_llm_models(conn, config)
                if self._count(conn, "runtime_query_synonyms_count.sql") == 0:
                    seeded["query_synonyms"] = self._seed_query_synonyms(conn, config)
                if self._count(conn, "runtime_prompt_banned_count.sql") == 0:
                    seeded["prompt_security_banned_phrases"] = self._seed_banned_phrases(conn, config)
                if self._count(conn, "runtime_rerank_profiles_count.sql") == 0:
                    seeded["rerank_profiles"] = self._seed_rerank_profiles(conn, config)
                if self._count(conn, "runtime_chunk_categories_count.sql") == 0:
                    seeded["chunk_categories"] = self._seed_chunk_categories(conn, config)
                if self._count(conn, "runtime_equation_patterns_count.sql") == 0:
                    seeded["equation_patterns"] = self._seed_equation_patterns(conn, config)
        except UndefinedTable:
            return {}
        return {key: value for key, value in seeded.items() if value}

    def load(self) -> dict[str, Any]:
        if not self.database.configured:
            return {}

        try:
            with self.database.connection() as conn:
                loaded = {}
                loaded.update(self._load_llm_models(conn))
                loaded["QUERY_SYNONYMS"] = self._load_query_synonyms(conn)
                loaded["PROMPT_SECURITY"] = {"BANNED_PHRASES": self._load_banned_phrases(conn)}
                loaded["RERANK_PROFILES"] = self._load_rerank_profiles(conn)
                loaded["CHUNK_CATEGORIES"] = self._load_chunk_categories(conn)
                loaded["EQUATION_DETECTION"] = self._load_equation_detection(conn)
        except UndefinedTable:
            return {}

        return {key: value for key, value in loaded.items() if value not in (None, [], {})}

    def apply_to_config(self, config_wrapper) -> dict[str, Any]:
        loaded = self.load()
        target = getattr(config_wrapper, "config", None)
        if isinstance(target, dict):
            target.update(loaded)
        return loaded

    def admin_catalog(self) -> dict[str, Any]:
        if not self.database.configured:
            return {
                "llmModels": [],
                "rerankProfiles": [],
                "equationPatterns": [],
            }

        try:
            with self.database.connection() as conn:
                llm_models = conn.execute(load_query("runtime_llm_models_admin_list.sql")).fetchall()
                rerank_profiles = conn.execute(load_query("runtime_rerank_profiles_admin_list.sql")).fetchall()
                equation_patterns = conn.execute(load_query("runtime_equation_patterns_admin_list.sql")).fetchall()
        except UndefinedTable:
            return {
                "llmModels": [],
                "rerankProfiles": [],
                "equationPatterns": [],
            }

        return {
            "llmModels": [
                {
                    "id": int(row["id"]),
                    "modelName": row["model_name"],
                    "displayName": row["display_name"],
                    "provider": row["provider"],
                    "isDefault": bool(row["is_default"]),
                    "isEnabled": bool(row["is_enabled"]),
                    "temperature": float(row["temperature"]),
                    "numPredict": int(row["num_predict"]),
                    "numCtx": int(row["num_ctx"]) if row["num_ctx"] is not None else None,
                    "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
                for row in llm_models
            ],
            "rerankProfiles": [
                {
                    "id": int(row["id"]),
                    "name": row["name"],
                    "weightVector": float(row["weight_vector"]),
                    "weightRerank": float(row["weight_rerank"]),
                    "isDefault": bool(row["is_default"]),
                    "keywords": list(row["keywords"] or []),
                    "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
                for row in rerank_profiles
            ],
            "equationPatterns": [
                {
                    "id": int(row["id"]),
                    "patternType": row["pattern_type"],
                    "pattern": row["pattern"],
                    "isRegex": bool(row["is_regex"]),
                    "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in equation_patterns
            ],
        }

    def _count(self, conn, query_name: str) -> int:
        row = conn.execute(load_query(query_name)).fetchone()
        return int(row["count"] or 0)

    def _seed_llm_models(self, conn, config: dict[str, Any]) -> int:
        rows = self._llm_seed_rows(config)
        if not rows:
            return 0

        conn.execute(load_query("runtime_llm_models_clear_default.sql"))
        for row in rows:
            conn.execute(
                load_query("runtime_llm_models_upsert.sql"),
                (
                    row["model_name"],
                    row["display_name"],
                    row["provider"],
                    row["is_default"],
                    row["is_enabled"],
                    row["temperature"],
                    row["num_predict"],
                    row["num_ctx"],
                ),
            )
        return len(rows)

    def _seed_query_synonyms(self, conn, config: dict[str, Any]) -> int:
        count = 0
        for canonical, synonym in self._query_synonym_rows(config.get("QUERY_SYNONYMS", [])):
            conn.execute(load_query("runtime_query_synonyms_insert.sql"), (canonical, synonym))
            count += 1
        return count

    def _seed_banned_phrases(self, conn, config: dict[str, Any]) -> int:
        phrases = config.get("PROMPT_SECURITY", {}).get("BANNED_PHRASES", [])
        count = 0
        for phrase in phrases:
            phrase = str(phrase).strip()
            if not phrase:
                continue
            conn.execute(load_query("runtime_prompt_banned_insert.sql"), (phrase,))
            count += 1
        return count

    def _seed_rerank_profiles(self, conn, config: dict[str, Any]) -> int:
        profiles = config.get("RERANK_PROFILES", {}) or {}
        count = 0
        for name, values in profiles.items():
            if not isinstance(values, dict):
                continue
            row = conn.execute(
                load_query("runtime_rerank_profile_upsert.sql"),
                (
                    str(name),
                    float(values.get("weight_vector", 0.4)),
                    float(values.get("weight_rerank", 0.8)),
                    str(name) == "default",
                ),
            ).fetchone()
            profile_id = row["id"]
            for keyword in values.get("keywords", []):
                keyword = str(keyword).strip()
                if keyword:
                    conn.execute(load_query("runtime_rerank_keyword_insert.sql"), (profile_id, keyword, 1.0))
            count += 1
        return count

    def _seed_chunk_categories(self, conn, config: dict[str, Any]) -> int:
        categories = config.get("CHUNK_CATEGORIES", {}) or {}
        count = 0
        for name, values in categories.items():
            if not isinstance(values, dict):
                continue
            row = conn.execute(
                load_query("runtime_chunk_category_upsert.sql"),
                (
                    str(name),
                    str(values.get("detail_level") or name),
                    float(values.get("priority", 0.0)),
                ),
            ).fetchone()
            category_id = row["id"]
            for keyword in values.get("keywords", []):
                keyword = str(keyword).strip()
                if keyword:
                    conn.execute(load_query("runtime_chunk_category_keyword_insert.sql"), (category_id, keyword))
            count += 1
        return count

    def _seed_equation_patterns(self, conn, config: dict[str, Any]) -> int:
        equation = config.get("EQUATION_DETECTION", {}) or {}
        pattern_groups = {
            "symbol": equation.get("MATH_SYMBOLS", []),
            "keyword": equation.get("KEYWORDS", []),
            "ocr_caption_keyword": equation.get("OCR_CAPTION_KEYWORDS", []),
            "variable_definition": equation.get("MATH_VARIABLE_DEFINITION_PATTERNS", []),
        }
        count = 0
        for pattern_type, patterns in pattern_groups.items():
            for pattern in patterns:
                pattern = str(pattern).strip()
                if not pattern:
                    continue
                conn.execute(
                    load_query("runtime_equation_pattern_insert.sql"),
                    (pattern_type, pattern, pattern_type in {"symbol", "variable_definition"}),
                )
                count += 1
        return count

    def _load_llm_models(self, conn) -> dict[str, Any]:
        rows = conn.execute(load_query("runtime_llm_models_enabled.sql")).fetchall()
        if not rows:
            return {}
        default = next((row for row in rows if row["is_default"]), rows[0])
        loaded = {
            "LLM_MODEL_OPTIONS": [row["model_name"] for row in rows],
            "LLM_MODEL_NAME": default["model_name"],
            "LLM_TEMPERATURE": float(default["temperature"]),
            "LLM_NUM_PREDICT": int(default["num_predict"]),
        }
        if default["num_ctx"] is not None:
            loaded["LLM_NUM_CTX"] = int(default["num_ctx"])
        return loaded

    def _load_query_synonyms(self, conn) -> list[list[str]]:
        rows = conn.execute(load_query("runtime_query_synonyms_list.sql")).fetchall()
        return [[row["canonical_term"], row["synonym"]] for row in rows]

    def _load_banned_phrases(self, conn) -> list[str]:
        rows = conn.execute(load_query("runtime_prompt_banned_list.sql")).fetchall()
        return [row["phrase"] for row in rows]

    def _load_rerank_profiles(self, conn) -> dict[str, dict[str, Any]]:
        rows = conn.execute(load_query("runtime_rerank_profiles_load.sql")).fetchall()
        profiles = {}
        for row in rows:
            profiles[row["name"]] = {
                "weight_vector": float(row["weight_vector"]),
                "weight_rerank": float(row["weight_rerank"]),
                "keywords": list(row["keywords"] or []),
            }
        return profiles

    def _load_chunk_categories(self, conn) -> dict[str, dict[str, Any]]:
        rows = conn.execute(load_query("runtime_chunk_categories_load.sql")).fetchall()
        categories = {}
        for row in rows:
            categories[row["name"]] = {
                "detail_level": row["detail_level"],
                "priority": float(row["priority"]),
                "keywords": list(row["keywords"] or []),
            }
        return categories

    def _load_equation_detection(self, conn) -> dict[str, list[str]]:
        rows = conn.execute(load_query("runtime_equation_patterns_load.sql")).fetchall()
        mapping = {
            "symbol": "MATH_SYMBOLS",
            "keyword": "KEYWORDS",
            "ocr_caption_keyword": "OCR_CAPTION_KEYWORDS",
            "variable_definition": "MATH_VARIABLE_DEFINITION_PATTERNS",
        }
        detection = {value: [] for value in mapping.values()}
        for row in rows:
            key = mapping.get(row["pattern_type"])
            if key:
                detection[key].append(row["pattern"])
        return {key: value for key, value in detection.items() if value}

    @staticmethod
    def _llm_seed_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
        default_name = str(config.get("LLM_MODEL_NAME") or "").strip()
        options = config.get("LLM_MODEL_OPTIONS") or []
        if isinstance(options, str):
            options = [options]

        names = []
        for option in options:
            if isinstance(option, dict):
                name = str(option.get("model_name") or option.get("name") or "").strip()
            else:
                name = str(option).strip()
            if name and name not in names:
                names.append(name)
        if default_name and default_name not in names:
            names.insert(0, default_name)

        return [
            {
                "model_name": name,
                "display_name": name,
                "provider": "ollama",
                "is_default": name == default_name or (not default_name and index == 0),
                "is_enabled": True,
                "temperature": float(config.get("LLM_TEMPERATURE", 0.2)),
                "num_predict": int(config.get("LLM_NUM_PREDICT", 3072)),
                "num_ctx": config.get("LLM_NUM_CTX"),
            }
            for index, name in enumerate(names)
        ]

    @staticmethod
    def _query_synonym_rows(raw_pairs: Any) -> list[tuple[str, str]]:
        rows = []
        for pair in raw_pairs or []:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            canonical = str(pair[0]).strip().lower()
            synonym = str(pair[1]).strip().lower()
            if canonical and synonym:
                rows.append((canonical, synonym))
        return rows
