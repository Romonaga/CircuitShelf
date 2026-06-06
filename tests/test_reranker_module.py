import unittest

from backend.services.reranker import Reranker


class RerankerProfileTests(unittest.TestCase):
    def test_profile_keywords_can_be_numeric_yaml_values(self):
        reranker = Reranker.__new__(Reranker)
        reranker.rerank_profiles = {
            "default": {"weight_vector": 0.4, "weight_rerank": 0.6, "keywords": ["pin"]},
            "timer": {"weight_vector": 0.5, "weight_rerank": 0.5, "keywords": [555]},
        }

        fused, profile = reranker.fuse_scores_with_ranks([(0, 1.0)], [0.9], "555 timer")

        self.assertEqual(profile, "timer")
        self.assertEqual(len(fused), 1)

    def test_profile_weights_are_normalized_before_fusing(self):
        reranker = Reranker.__new__(Reranker)
        vector, rerank = reranker.normalized_weights({"weight_vector": 0.4, "weight_rerank": 0.8})

        self.assertAlmostEqual(vector + rerank, 1.0)
        self.assertAlmostEqual(vector, 1 / 3)
        self.assertAlmostEqual(rerank, 2 / 3)

    def test_effective_batch_size_uses_resolver(self):
        reranker = Reranker.__new__(Reranker)
        reranker.batch_size_resolver = lambda: 96
        reranker.config = {"RERANK_BATCH_SIZE": 32}

        self.assertEqual(reranker.effective_batch_size(), 96)

    def test_rerank_chunks_caps_context_payload_after_scoring(self):
        class State:
            def __init__(self):
                self.chunk_metadata = [{"source": "doc.pdf"} for _ in range(6)]
                self.sources = ["doc.pdf"] * 6

            def get_chunks(self):
                return [f"chunk {index}" for index in range(6)]

        class Encoder:
            def predict(self, _inputs, **_kwargs):
                return [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]

        class Chunker:
            def compute_confidence(self, *_args, **_kwargs):
                return 0.88

        reranker = Reranker.__new__(Reranker)
        reranker.config = {
            "MIN_ACCEPTED_SCORE": 0.0,
            "RERANK_MAX_CONTEXT_CHUNKS": 3,
            "RERANK_PROFILES": {"default": {"weight_vector": 0.4, "weight_rerank": 0.6, "keywords": []}},
        }
        reranker.rerank_profiles = reranker.config["RERANK_PROFILES"]
        reranker.cross_encoder = Encoder()
        reranker.state = State()
        reranker.chunker = Chunker()
        reranker.device = None
        reranker.batch_size_resolver = lambda: 8

        payload, confidence, profile = reranker.rerank_chunks([(idx, 1.0 + idx) for idx in range(6)], "555 timer")

        self.assertEqual(len(payload), 3)
        self.assertEqual(confidence, "0.88")
        self.assertEqual(profile, "default")


if __name__ == "__main__":
    unittest.main()
