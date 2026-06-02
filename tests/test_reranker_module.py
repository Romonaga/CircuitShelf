import unittest

from reranker_module import Reranker


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


if __name__ == "__main__":
    unittest.main()
