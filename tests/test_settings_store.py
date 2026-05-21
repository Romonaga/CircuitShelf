import unittest

from db.settings import AppSettingsStore


class AppSettingsStoreTests(unittest.TestCase):
    def test_typed_values_preserve_scalar_types(self):
        store = AppSettingsStore(None)

        self.assertEqual(store._typed_values(True), ("boolean", None, None, None, True))
        self.assertEqual(store._typed_values(12), ("integer", None, 12, None, None))
        self.assertEqual(store._typed_values("abc"), ("text", "abc", None, None, None))
        self.assertEqual(store._typed_values(0.25)[0], "numeric")

    def test_does_not_store_bootstrap_settings_or_complex_values(self):
        store = AppSettingsStore(None)

        self.assertFalse(store._should_store("DATABASE_URL", "postgresql://example"))
        self.assertFalse(store._should_store("QUERY_SYNONYMS", []))
        self.assertTrue(store._should_store("CHUNK_SIZE", 500))


if __name__ == "__main__":
    unittest.main()
