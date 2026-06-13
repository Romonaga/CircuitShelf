import unittest
from contextlib import contextmanager

import numpy as np

from db.vector_store import bool_from_meta, vector_from_sql, vector_to_sql, VectorStore


class VectorStoreHelperTests(unittest.TestCase):
    def test_vector_round_trip_uses_pgvector_text_format(self):
        encoded = vector_to_sql(np.asarray([0.125, -2.5, 3.0], dtype="float32"))

        self.assertEqual(encoded, "[0.125,-2.5,3]")
        np.testing.assert_allclose(vector_from_sql(encoded), np.asarray([0.125, -2.5, 3.0], dtype="float32"))

    def test_bool_from_metadata_accepts_common_truthy_values(self):
        self.assertTrue(bool_from_meta(True))
        self.assertTrue(bool_from_meta("yes"))
        self.assertTrue(bool_from_meta("1"))
        self.assertFalse(bool_from_meta(False))
        self.assertFalse(bool_from_meta(None))
        self.assertFalse(bool_from_meta("no"))

    def test_rel_path_prefers_training_relative_paths(self):
        store = VectorStore(None, "training", "embedder")

        self.assertEqual(store.rel_path_for_source("training/books/ne555.pdf", {}), "books/ne555.pdf")
        self.assertEqual(
            store.rel_path_for_source("ignored", {"parent_source": "training/ne556.pdf"}),
            "ne556.pdf",
        )

    def test_page_number_rejects_invalid_values(self):
        self.assertEqual(VectorStore.page_number({"page": "7"}), 7)
        self.assertIsNone(VectorStore.page_number({"page": "0"}))
        self.assertIsNone(VectorStore.page_number({"page": "unknown"}))

    def test_prune_document_chunks_below_quality_runs_threshold_query(self):
        class FakeResult:
            def fetchone(self):
                return {"pruned_chunks": 3, "pruned_image_chunks": 1}

        class FakeConnection:
            def __init__(self):
                self.executed = []

            def execute(self, query, params):
                self.executed.append((query, params))
                return FakeResult()

        class FakeDatabase:
            def __init__(self):
                self.conn = FakeConnection()

            @contextmanager
            def connection(self):
                yield self.conn

        database = FakeDatabase()
        store = VectorStore(database, "training", "embedder")

        result = store.prune_document_chunks_below_quality("doc.pdf", 0.35)

        self.assertEqual(result, {"prunedChunks": 3, "prunedImageChunks": 1})
        self.assertIn("DELETE FROM document_chunks", database.conn.executed[0][0])
        self.assertEqual(database.conn.executed[0][1], ("doc.pdf", 0.35))

    def test_prune_document_chunks_below_quality_noops_without_threshold(self):
        class FakeDatabase:
            @contextmanager
            def connection(self):
                raise AssertionError("database should not be queried")

        store = VectorStore(FakeDatabase(), "training", "embedder")

        self.assertEqual(store.prune_document_chunks_below_quality("doc.pdf", None), {"prunedChunks": 0, "prunedImageChunks": 0})
        self.assertEqual(store.prune_document_chunks_below_quality("doc.pdf", 0), {"prunedChunks": 0, "prunedImageChunks": 0})


if __name__ == "__main__":
    unittest.main()
