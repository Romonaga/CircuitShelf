from sentence_transformers import CrossEncoder

class Reranker:
    def __init__(self, config, state, chunker, trace_logger):
        self.config = config
        self.state = state
        self.chunker = chunker
        self.trace_logger = trace_logger

        self.rerank_profiles = config.get("RERANK_PROFILES")
        self.model_name = config.get("CROSS_ENCODER_MODEL")
        self.cross_encoder = CrossEncoder(self.model_name)
        
  

    def rerank_chunks(self, dedup_hits, question):
        chunks = self.state.get_chunks()
        texts = [chunks[i] for i, _ in dedup_hits]

       
        combined_inputs = [[question, t] for t in texts]
        
        # Predict CrossEncoder (reranker) scores
        scores = self.cross_encoder.predict(combined_inputs).tolist()

        # Fuse FAISS + reranker scores
        fused, profile = self.fuse_scores_with_ranks(dedup_hits, scores, question)

        # Filter by minimum accepted score
        min_score = self.config.get("MIN_ACCEPTED_SCORE", 0.1)
        filtered = [entry for entry in fused if entry[3] >= min_score]

        if not filtered:
            self.trace_logger.warning(f"⚠️ No reranked chunks passed min score ({min_score})")
            return [], "0.00", profile

        top_score = filtered[0][3]
        second_score = filtered[1][3] if len(filtered) > 1 else 0
        confidence = self.chunker.compute_confidence(top_score, second_score, method="sigmoid_margin")

        selected = [(idx, dist) for idx, dist, _, _ in filtered]
        return self.build_chunk_payload(selected), f"{confidence:.2f}", profile

    def fuse_scores_with_ranks(self, faiss_hits, rerank_scores, question):
        q_lower = question.lower()
        profile = "default"
        for pname, pdata in self.rerank_profiles.items():
            if any(kw in q_lower for kw in pdata.get("keywords", [])):
                profile = pname
                break

        weights = self.rerank_profiles.get(profile, self.rerank_profiles["default"])
        w_faiss = weights.get("weight_faiss", 0.4)
        w_rerank = weights.get("weight_rerank", 0.6)

        # Normalize FAISS distances to scores in [0, 1]
        faiss_scores = [1.0 - min(d / 15.0, 1.0) for _, d in faiss_hits]
        fused = []
        for (i, dist), f_score, r_score in zip(faiss_hits, faiss_scores, rerank_scores):
            combined = w_faiss * f_score + w_rerank * r_score
            fused.append((i, dist, r_score, combined))

        fused.sort(key=lambda x: x[3], reverse=True)
        return fused, profile

    def build_chunk_payload(self, selected_hits):
        chunks = self.state.get_chunks()
        metadata = self.state.chunk_metadata
        sources = self.state.sources

        return [{
            "text": chunks[i],
            "index": i,
            "distance": d,
            "section": metadata[i].get("section", "Unknown"),
            "source": sources[i],
            "category": metadata[i].get("category", "Uncategorized")
        } for i, d in selected_hits]
