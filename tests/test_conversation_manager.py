import unittest

from backend.services.conversation_manager import (
    append_chat_turn,
    build_chat_messages,
    build_contextual_retrieval_query,
    clean_history_text,
    normalize_chat_history,
)


class ConversationManagerTests(unittest.TestCase):
    def test_clean_history_text_removes_rendered_image_html(self):
        dirty = (
            "🧠 Answer\n\nUse pin 1 for ground.\n\n---\n\n"
            "🖼️ Related Images\n\n<img src=\"data:image/png;base64,abc\" />"
        )

        self.assertEqual(clean_history_text(dirty), "Use pin 1 for ground.")

    def test_normalize_chat_history_accepts_pairs_and_limits_budget(self):
        history = [
            ["first question", "first answer"],
            ["second question", "second answer"],
            ["third question", "third answer"],
        ]

        turns = normalize_chat_history(history, max_turns=2, max_chars=1000)

        self.assertEqual([turn.question for turn in turns], ["second question", "third question"])

    def test_build_chat_messages_uses_roles(self):
        messages = build_chat_messages(
            "system prompt",
            "current prompt",
            [["what is pin 1?", "ground"]],
            max_turns=5,
            max_chars=1000,
        )

        self.assertEqual(
            messages,
            [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "what is pin 1?"},
                {"role": "assistant", "content": "ground"},
                {"role": "user", "content": "current prompt"},
            ],
        )

    def test_contextual_retrieval_query_includes_recent_history(self):
        query = build_contextual_retrieval_query(
            "what capacitor value should I use?",
            [["wire a 555 astable timer", "Use the NE555 astable configuration."]],
        )

        self.assertIn("wire a 555 astable timer", query)
        self.assertIn("what capacitor value should I use?", query)

    def test_append_chat_turn_returns_frontend_pairs(self):
        history = append_chat_turn([], "question", "answer")

        self.assertEqual(history, [["question", "answer"]])


if __name__ == "__main__":
    unittest.main()
