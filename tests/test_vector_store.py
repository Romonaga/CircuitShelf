import unittest

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


if __name__ == "__main__":
    unittest.main()
