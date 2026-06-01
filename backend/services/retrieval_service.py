import re
from collections import OrderedDict


class QueryPreprocessor:
    def __init__(self, *, config, trace_logger, banned_phrases: list[str]):
        self.config = config
        self.trace_logger = trace_logger
        self.banned_phrases = banned_phrases

    def sanitize(self, user_input: str) -> str:
        sanitized = user_input or ""
        for phrase in self.banned_phrases:
            sanitized = re.sub(phrase, "[REDACTED]", sanitized, flags=re.IGNORECASE)
        return sanitized

    def normalize(self, question: str) -> str:
        sanitized = self.sanitize(question)
        return re.sub(r"\s+", " ", sanitized.strip().lower())

    def expand(self, query: str) -> list[str]:
        synonym_pairs = self.config.get("QUERY_SYNONYMS", [])
        synonyms = set()
        query_lower = str(query).lower()

        for pair in synonym_pairs:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                self.trace_logger.warning(f"⚠️ Invalid QUERY_SYNONYMS entry skipped: {pair!r}")
                continue
            orig, repl = (str(pair[0]).lower(), str(pair[1]).lower())
            if orig in query_lower:
                synonyms.add(query_lower.replace(orig, repl))

        synonyms.add(query_lower)
        return list(OrderedDict.fromkeys(synonyms))


class RuntimeChunkMapper:
    def __init__(self, *, state, vector_store, trace_logger):
        self.state = state
        self.vector_store = vector_store
        self.trace_logger = trace_logger

    @staticmethod
    def deduplicate_hits_by_index(hits: list[tuple[int, float]]) -> list[tuple[int, float]]:
        best_by_index = {}
        for idx, distance in hits:
            if idx not in best_by_index or distance < best_by_index[idx]:
                best_by_index[idx] = distance
        return sorted(best_by_index.items(), key=lambda item: item[1])

    def build_db_chunk_index(self) -> dict[tuple[str, int], int]:
        mapping = {}
        per_source_counts = {}
        metadata = self.state.get_metadata()
        sources = self.state.get_sources()
        for idx, source in enumerate(sources):
            meta = metadata[idx] if idx < len(metadata) else {}
            rel_path = meta.get("db_source_path") or self.vector_store.rel_path_for_source(source, meta)
            chunk_index = meta.get("db_chunk_index")
            if chunk_index is None:
                chunk_index = per_source_counts.get(rel_path, 0)
            per_source_counts[rel_path] = int(chunk_index) + 1
            mapping[(rel_path, int(chunk_index))] = idx
        return mapping

    def vector_results_to_hits(self, results: list[dict]) -> list[tuple[int, float]]:
        index_by_key = self.build_db_chunk_index()
        hits = []
        for result in results:
            rel_path = self.vector_store.rel_path_for_source(result.get("source", ""), {})
            key = (rel_path, int(result.get("chunk_index", 0)))
            idx = index_by_key.get(key)
            if idx is None:
                self.trace_logger.warning(f"⚠️ Retrieved DB chunk not found in runtime state: {key}")
                continue
            hits.append((idx, float(result.get("distance", 0.0))))
        return hits
