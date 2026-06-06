from sentence_transformers import CrossEncoder

from backend.services.model_runtime import release_accelerator_memory


class Reranker:
    def __init__(
        self,
        config,
        state,
        chunker,
        trace_logger,
        *,
        device=None,
        batch_size_resolver=None,
        lazy=False,
        gpu_coordinator=None,
        gpu_priority: int = 30,
        gpu_owner: str = "web",
    ):
        self.config = config
        self.state = state
        self.chunker = chunker
        self.trace_logger = trace_logger
        self.device = device
        self.batch_size_resolver = batch_size_resolver
        self.lazy = bool(lazy)
        self.gpu_coordinator = gpu_coordinator
        self.gpu_priority = int(gpu_priority)
        self.gpu_owner = gpu_owner

        self.rerank_profiles = config.get("RERANK_PROFILES")
        self.model_name = config.get("CROSS_ENCODER_MODEL")
        self.cross_encoder = None if self.lazy else CrossEncoder(self.model_name, device=device)

    @property
    def resident(self) -> bool:
        return self.cross_encoder is not None

    def _ensure_cross_encoder(self):
        if self.cross_encoder is None:
            self.trace_logger.info(f"🧠 Cold-loading reranker model on device: {self.device}")
            self.cross_encoder = CrossEncoder(self.model_name, device=self.device)
        return self.cross_encoder

    def unload(self) -> bool:
        if self.cross_encoder is None:
            return False
        self.cross_encoder = None
        self.trace_logger.info("🧹 Unloaded idle reranker model from ingest worker.")
        release_accelerator_memory(self.trace_logger)
        return True

    def rerank_chunks(self, dedup_hits, question):
        if not dedup_hits:
            return [], "0.00", "default"

        chunks = self.state.get_chunks()
        texts = [chunks[i] for i, _ in dedup_hits]

        combined_inputs = [[question, t] for t in texts]

        batch_size = self.effective_batch_size()
        raw_scores = self._predict(combined_inputs, batch_size)
        if hasattr(raw_scores, "tolist"):
            raw_scores = raw_scores.tolist()
        scores = self.normalize_rerank_scores(raw_scores)

        # Fuse vector-distance and reranker scores.
        fused, profile = self.fuse_scores_with_ranks(dedup_hits, scores, question)

        # Filter by minimum accepted score
        min_score = self.config.get("MIN_ACCEPTED_SCORE", 0.1)
        filtered = [entry for entry in fused if entry[3] >= min_score]

        if not filtered:
            fallback_limit = self.config.get("RERANK_FALLBACK_TOP_K", 8)
            selected = fused[:fallback_limit]
            if not selected:
                self.trace_logger.warning(f"⚠️ No reranked chunks passed min score ({min_score})")
                return [], "0.00", profile

            top_score = selected[0][3]
            second_score = selected[1][3] if len(selected) > 1 else 0
            confidence = self.chunker.compute_confidence(top_score, second_score, method="sigmoid_margin")
            self.trace_logger.warning(
                f"⚠️ Reranked chunks were below min score ({min_score}); using top "
                f"{len(selected)} retrieved chunks as low-confidence context."
            )
            selected_hits = [(idx, dist) for idx, dist, _, _ in selected]
            return self.build_chunk_payload(selected_hits), f"{confidence:.2f}", f"{profile} (below threshold)"

        top_score = filtered[0][3]
        second_score = filtered[1][3] if len(filtered) > 1 else 0
        confidence = self.chunker.compute_confidence(top_score, second_score, method="sigmoid_margin")

        max_context_chunks = max(1, int(self.config.get("RERANK_MAX_CONTEXT_CHUNKS", 15)))
        selected = [(idx, dist) for idx, dist, _, _ in filtered[:max_context_chunks]]
        return self.build_chunk_payload(selected), f"{confidence:.2f}", profile

    def normalize_rerank_scores(self, scores):
        if not scores:
            return []

        low = min(scores)
        high = max(scores)
        if 0.0 <= low and high <= 1.0:
            return scores
        if high == low:
            return [0.5 for _ in scores]
        return [(score - low) / (high - low) for score in scores]

    def fuse_scores_with_ranks(self, vector_hits, rerank_scores, question):
        q_lower = str(question).lower()
        profile = "default"
        profiles = self.rerank_profiles or {}
        for pname, pdata in profiles.items():
            keywords = [str(kw).lower() for kw in pdata.get("keywords", [])]
            if any(kw in q_lower for kw in keywords):
                profile = pname
                break

        weights = profiles.get(profile) or profiles.get("default") or {}
        w_vector, w_rerank = self.normalized_weights(weights)

        vector_scores = [1.0 - min(d / 15.0, 1.0) for _, d in vector_hits]
        fused = []
        for (i, dist), vector_score, r_score in zip(vector_hits, vector_scores, rerank_scores):
            combined = w_vector * vector_score + w_rerank * r_score
            fused.append((i, dist, r_score, combined))

        fused.sort(key=lambda x: x[3], reverse=True)
        return fused, profile

    def effective_batch_size(self):
        if self.batch_size_resolver:
            return max(1, int(self.batch_size_resolver()))
        return max(1, int(self.config.get("RERANK_BATCH_SIZE", 32)))

    def _predict(self, combined_inputs, batch_size):
        gpu_coordinator = getattr(self, "gpu_coordinator", None)
        if not gpu_coordinator:
            return self._ensure_cross_encoder().predict(
                combined_inputs,
                batch_size=batch_size,
                show_progress_bar=False,
                device=self.device,
            )
        with gpu_coordinator.lease(
            task_type="rerank",
            resource_class="cuda_batch",
            priority=getattr(self, "gpu_priority", 30),
            owner=getattr(self, "gpu_owner", "web"),
            details={"pairs": len(combined_inputs), "batchSize": batch_size},
        ):
            return self._ensure_cross_encoder().predict(
                combined_inputs,
                batch_size=batch_size,
                show_progress_bar=False,
                device=self.device,
            )

    @staticmethod
    def normalized_weights(weights):
        vector = float(weights.get("weight_vector", 0.4))
        rerank = float(weights.get("weight_rerank", 0.6))
        total = vector + rerank
        if total <= 0:
            return 0.4, 0.6
        return vector / total, rerank / total

    def build_chunk_payload(self, selected_hits):
        chunks = self.state.get_chunks()
        metadata = self.state.chunk_metadata
        sources = self.state.sources

        payload = []
        for i, d in selected_hits:
            meta = metadata[i]
            payload.append({
                "text": chunks[i],
                "index": i,
                "distance": d,
                "section": meta.get("section", "Unknown"),
                "source": meta.get("parent_source") or meta.get("source") or sources[i],
                "source_image_id": meta.get("source_image_id"),
                "page": meta.get("page"),
                "category": meta.get("category", "Uncategorized")
            })
        return payload
