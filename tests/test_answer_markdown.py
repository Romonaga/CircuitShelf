import unittest

from backend.services.answer_markdown import normalize_answer_markdown


class AnswerMarkdownTests(unittest.TestCase):
    def test_normalizes_flat_markdown_for_display_storage(self):
        raw = (
            "Short answer. --- ## Section - First point - Second point "
            "## Table | A | B | |---|---| | one | two | | three | four |"
        )

        normalized = normalize_answer_markdown(raw)

        self.assertIn("\n\n---\n\n", normalized)
        self.assertIn("\n\n## Section", normalized)
        self.assertIn("\n- First point", normalized)
        self.assertIn("\n\n## Table", normalized)
        self.assertIn("| A | B |", normalized)
        self.assertIn("| one | two |", normalized)


if __name__ == "__main__":
    unittest.main()
