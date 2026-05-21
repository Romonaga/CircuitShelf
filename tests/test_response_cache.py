import os
import tempfile
import unittest

from response_cache import (
    ResponseCache,
    ResponseCacheEntry,
    ResponseCacheKey,
    build_index_fingerprint,
    should_cache_response,
)


class ResponseCacheTests(unittest.TestCase):
    def make_key(self, **overrides):
        values = {
            "index_fingerprint": "index-a",
            "model": "electronics-helper:latest",
            "strategy": "FAISS + CrossEncoder",
            "question": "what is pin 1?",
            "retrieval_query": "what is pin 1?",
            "top_k": 15,
            "distance_threshold": 4.0,
            "max_tokens": 1800,
            "show_full_text": False,
        }
        values.update(overrides)
        return ResponseCacheKey(**values)

    def test_cache_key_changes_when_index_changes(self):
        self.assertNotEqual(
            self.make_key(index_fingerprint="index-a").digest(),
            self.make_key(index_fingerprint="index-b").digest(),
        )

    def test_cache_key_includes_retrieval_settings(self):
        self.assertNotEqual(
            self.make_key(top_k=5).digest(),
            self.make_key(top_k=15).digest(),
        )

    def test_response_cache_round_trip(self):
        cache = ResponseCache(capacity=2)
        key = self.make_key()
        entry = ResponseCacheEntry(
            answer="Pin 1 is ground.",
            chat_history=[["what is pin 1?", "Pin 1 is ground."]],
            sources=["training/ne555.pdf"],
            confidence="0.97",
        )

        self.assertIsNone(cache.get_response(key))
        cache.put_response(key, entry)
        self.assertEqual(cache.get_response(key).answer, "Pin 1 is ground.")
        self.assertEqual(cache.stats()["hits"], 1)
        self.assertEqual(cache.stats()["misses"], 1)

    def test_response_cache_skips_conversation_history(self):
        self.assertTrue(should_cache_response([], bypass_cache=False))
        self.assertFalse(should_cache_response([["prior", "answer"]], bypass_cache=False))
        self.assertFalse(should_cache_response([], bypass_cache=True))

    def test_index_fingerprint_uses_manifest_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write('{"files":{"a.pdf":{"size":1}}}')
            first = build_index_fingerprint(
                manifest_path=manifest_path,
                chunks_count=1,
                embeddings_count=1,
                faiss_total=1,
            )

            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write('{"files":{"b.pdf":{"size":1}}}')
            second = build_index_fingerprint(
                manifest_path=manifest_path,
                chunks_count=1,
                embeddings_count=1,
                faiss_total=1,
            )

        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
