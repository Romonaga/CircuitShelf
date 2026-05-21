import unittest

from db.query_log_store import QueryLogStore


class QueryLogStoreHelperTests(unittest.TestCase):
    def test_db_source_path_normalizes_training_prefix(self):
        self.assertEqual(QueryLogStore._db_source_path("training/books/ne555.pdf"), "books/ne555.pdf")
        self.assertEqual(QueryLogStore._db_source_path("ne555.pdf"), "ne555.pdf")

    def test_optional_float_handles_invalid_values(self):
        self.assertEqual(QueryLogStore._optional_float("0.95"), 0.95)
        self.assertIsNone(QueryLogStore._optional_float(None))
        self.assertIsNone(QueryLogStore._optional_float("not-a-number"))


if __name__ == "__main__":
    unittest.main()
