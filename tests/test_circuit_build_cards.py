import json
import unittest

from circuit_build_cards import build_recovery_prompt, parse_recovered_build_card


class CircuitBuildCardRecoveryTests(unittest.TestCase):
    def test_recovery_prompt_is_generic(self):
        prompt = build_recovery_prompt(
            "Build a breadboard circuit with a timer and microcontroller.",
            "Use the timer output as a digital input.",
            [{"source": "training/source.pdf", "displayName": "Source", "pages": [2], "chunkCount": 1, "chunks": []}],
        )

        self.assertIn("schema", prompt)
        self.assertIn("Build a breadboard circuit", prompt)

    def test_parse_recovered_build_card_validates_shape(self):
        raw = json.dumps(
            {
                "title": "Timer pulse reader",
                "componentName": "Timer and microcontroller",
                "componentType": "project",
                "summary": "Read timer pulses with a microcontroller.",
                "confidence": 0.7,
                "parts": [{"name": "Timer IC", "detail": "DIP package"}],
                "power": ["Use one regulated low-voltage supply."],
                "wiring": [
                    {"from": "Timer GND", "to": "Ground rail", "note": "Common ground"},
                    {"from": "Timer output", "to": "Microcontroller input", "note": "Read pulses"},
                ],
                "checks": ["Verify supply polarity."],
                "warnings": ["Confirm voltage compatibility."],
            }
        )

        card = parse_recovered_build_card(raw, [{"source": "training/source.pdf", "displayName": "Source", "pages": [2], "chunkCount": 1}])

        self.assertEqual(card["title"], "Timer pulse reader")
        self.assertEqual(len(card["wiring"]), 2)
        self.assertEqual(card["sourceNotes"][0]["source"], "Source")

    def test_parse_recovered_build_card_rejects_vague_output(self):
        self.assertIsNone(parse_recovered_build_card('{"title": "No wiring", "parts": []}', []))


if __name__ == "__main__":
    unittest.main()
