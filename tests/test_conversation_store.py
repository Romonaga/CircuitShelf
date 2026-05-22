import unittest

from db.conversation_store import ConversationStore


class ConversationStoreHelperTests(unittest.TestCase):
    def test_clean_title_uses_default_for_empty_values(self):
        self.assertEqual(ConversationStore._clean_title(""), "New conversation")
        self.assertEqual(ConversationStore._clean_title("   "), "New conversation")

    def test_clean_title_compacts_and_limits_text(self):
        title = ConversationStore._clean_title("  build   a   555 timer blink project  ")

        self.assertEqual(title, "build a 555 timer blink project")
        self.assertLessEqual(len(ConversationStore._clean_title("x" * 120)), 80)

    def test_optional_float_handles_invalid_values(self):
        self.assertEqual(ConversationStore._optional_float("0.75"), 0.75)
        self.assertIsNone(ConversationStore._optional_float(None))
        self.assertIsNone(ConversationStore._optional_float("bad"))


if __name__ == "__main__":
    unittest.main()
