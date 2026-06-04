from __future__ import annotations

import time
from typing import Any


class RagRetriever:
    def __init__(
        self,
        *,
        state: Any,
        embedder: Any,
        vector_store: Any,
        chunker: Any,
        reranker_engine: Any,
        runtime_chunk_mapper: Any,
        trace_logger: Any,
    ):
        self.state = state
        self.embedder = embedder
        self.vector_store = vector_store
        self.chunker = chunker
        self.reranker_engine = reranker_engine
        self.runtime_chunk_mapper = runtime_chunk_mapper
        self.trace_logger = trace_logger

    def retrieve(
        self,
        *,
        synonyms: list[str],
        retrieval_q: str,
        top_k: int,
        dist_thresh: float,
        strategy: str,
        entity_id: int | None,
    ) -> dict[str, Any]:
        all_hits = []
        vector_start = time.time()
        for synonym in synonyms:
            embedding = self.embedder.encode(
                [synonym],
                convert_to_numpy=True,
                normalize_embeddings=True,
            ).astype("float32")
            vector_results = self.vector_store.search_chunks(embedding[0], top_k=top_k, entity_id=entity_id)
            for index, distance in self.runtime_chunk_mapper.vector_results_to_hits(vector_results):
                adjusted = distance * (1 + 0.1 * (1 - len(self.state.chunks[index]) / 500))
                if adjusted < dist_thresh:
                    all_hits.append((index, adjusted))
        vector_duration = time.time() - vector_start

        if not all_hits:
            return {
                "selected_chunks": [],
                "confidence": "0.00",
                "profile": "N/A",
                "vector_duration": vector_duration,
                "rerank_duration": None,
                "hit_count": 0,
            }

        dedup_hits = self.runtime_chunk_mapper.deduplicate_hits_by_index(all_hits)
        rerank_duration = None

        if strategy == "Vector only":
            selected = sorted(dedup_hits, key=lambda x: x[1])[:top_k]
            selected_chunks = self.reranker_engine.build_chunk_payload(selected)
            confidence = self.chunker.compute_vector_confidence(selected, dist_thresh)
            profile = "N/A"
        else:
            rerank_start = time.time()
            selected_chunks, confidence, profile = self.reranker_engine.rerank_chunks(dedup_hits, retrieval_q)
            rerank_duration = time.time() - rerank_start
            if not selected_chunks:
                self.trace_logger.warning("⚠️ Reranker returned no chunks; falling back to top vector hits.")
                selected = sorted(dedup_hits, key=lambda x: x[1])[:top_k]
                selected_chunks = self.reranker_engine.build_chunk_payload(selected)
                confidence = self.chunker.compute_vector_confidence(selected, dist_thresh)
                profile = f"{profile} (vector fallback)"

        return {
            "selected_chunks": selected_chunks,
            "confidence": confidence,
            "profile": profile,
            "vector_duration": vector_duration,
            "rerank_duration": rerank_duration,
            "hit_count": len(all_hits),
        }
