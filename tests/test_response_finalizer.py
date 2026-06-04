import json
import unittest

from backend.services.response_finalizer import (
    build_response_finalizer_prompt,
    deterministic_response_issues,
    finalize_response,
    parse_response_finalizer_output,
    should_run_response_finalizer,
)


class ResponseFinalizerTests(unittest.TestCase):
    def test_detects_wiring_answer_missing_power_and_ground(self):
        issues = deterministic_response_issues(
            "wire this chip on a breadboard",
            "Connect pin 3 to the LED.",
            [{"source": "datasheet.pdf", "chunks": []}],
            None,
        )

        self.assertIn("The wiring answer does not mention ground/common-ground checks.", issues)
        self.assertIn("The wiring answer does not clearly state power or voltage requirements.", issues)

    def test_prompt_contains_schema_and_sources(self):
        prompt = build_response_finalizer_prompt(
            question="What is a 555?",
            answer="It is a timer.",
            source_payload=[
                {
                    "source": "training/ne555.pdf",
                    "displayName": "NE555",
                    "pages": [1],
                    "chunkCount": 1,
                    "chunks": [{"page": 1, "section": "Features", "preview": "555 timer"}],
                }
            ],
            build_card=None,
            deterministic_issues=[],
        )

        self.assertIn("Return ONLY this JSON shape", prompt)
        self.assertIn("training/ne555.pdf", prompt)

    def test_parse_revised_answer(self):
        raw = json.dumps(
            {
                "useful": True,
                "confidence": 0.82,
                "issues": ["Added missing warning."],
                "notes": ["Cleaned formatting."],
                "revisedAnswer": "## Answer\nUse common ground.",
            }
        )

        answer, validation = parse_response_finalizer_output(
            raw,
            fallback_answer="old answer",
            deterministic_issues=["Missing source citation."],
        )

        self.assertEqual(answer, "## Answer\nUse common ground.")
        self.assertTrue(validation.ran)
        self.assertTrue(validation.changed)
        self.assertEqual(validation.confidence, 0.82)
        self.assertIn("Missing source citation.", validation.issues)

    def test_should_run_modes(self):
        self.assertTrue(should_run_response_finalizer(enabled=True, mode="always", confidence=0.99, build_card=None, issues=[], min_confidence=0.8))
        self.assertFalse(should_run_response_finalizer(enabled=False, mode="always", confidence=0.1, build_card={}, issues=["x"], min_confidence=0.8))
        self.assertTrue(should_run_response_finalizer(enabled=True, mode="low_confidence", confidence=0.4, build_card=None, issues=[], min_confidence=0.8))
        self.assertFalse(should_run_response_finalizer(enabled=True, mode="issues", confidence=0.4, build_card=None, issues=[], min_confidence=0.8))

    def test_parse_marks_echoed_input_as_schema_issue(self):
        raw = json.dumps({"question": "What is this?", "answer": "Echoed answer"})

        answer, validation = parse_response_finalizer_output(
            raw,
            fallback_answer="Original answer",
            deterministic_issues=[],
        )

        self.assertEqual(answer, "Original answer")
        self.assertFalse(validation.useful)
        self.assertIn("Response finalizer did not return the requested review schema.", validation.issues)

    def test_finalize_response_uses_llm_call(self):
        def fake_llm(_prompt):
            return json.dumps(
                {
                    "useful": True,
                    "confidence": 0.9,
                    "issues": [],
                    "notes": ["Validated."],
                    "revisedAnswer": "Validated answer.",
                }
            )

        answer, validation = finalize_response(
            question="Explain this timer.",
            answer="Raw answer.",
            source_payload=[],
            build_card=None,
            model_name="test-model",
            confidence=0.9,
            enabled=True,
            mode="always",
            min_confidence=0.8,
            max_context_chars=1000,
            llm_call=fake_llm,
        )

        self.assertEqual(answer, "Validated answer.")
        self.assertEqual(validation.model, "test-model")
        self.assertTrue(validation.ran)


if __name__ == "__main__":
    unittest.main()
