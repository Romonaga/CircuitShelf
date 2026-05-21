import unittest
from datetime import datetime, timezone

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

    def test_coerce_value_validates_booleans_and_numbers(self):
        store = AppSettingsStore(None)

        self.assertTrue(store._coerce_value("boolean", "yes"))
        self.assertFalse(store._coerce_value("boolean", "off"))
        self.assertEqual(store._coerce_value("integer", "42"), 42)
        self.assertEqual(store._coerce_value("numeric", "0.25"), 0.25)

        with self.assertRaises(ValueError):
            store._coerce_value("boolean", "maybe")

    def test_api_row_uses_curated_ui_metadata(self):
        store = AppSettingsStore(None)
        row = {
            "key": "SITE_NAME",
            "value_type": "text",
            "text_value": "CircuitShelf",
            "integer_value": None,
            "numeric_value": None,
            "boolean_value": None,
            "description": "Imported from bootstrap config for SITE_NAME.",
            "is_sensitive": False,
            "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }

        api_row = store._api_row(row)

        self.assertEqual(api_row["label"], "Site name")
        self.assertEqual(api_row["group"], "general")
        self.assertEqual(api_row["groupLabel"], "General")
        self.assertEqual(api_row["description"], "Name shown in the web interface.")
        self.assertEqual(api_row["rawDescription"], "Imported from bootstrap config for SITE_NAME.")
        self.assertFalse(api_row["advanced"])

    def test_only_curated_non_sensitive_settings_are_ui_editable(self):
        store = AppSettingsStore(None)

        self.assertTrue(store._is_ui_editable({"key": "SITE_NAME", "is_sensitive": False}))
        self.assertFalse(store._is_ui_editable({"key": "UI_HOST", "is_sensitive": False}))
        self.assertFalse(store._is_ui_editable({"key": "DATABASE_URL", "is_sensitive": True}))


if __name__ == "__main__":
    unittest.main()
