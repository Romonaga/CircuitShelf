import json
import unittest

from backend.services.circuit_build_cards import build_circuit_build_card, build_recovery_prompt, parse_recovered_build_card


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

    def test_finder_candidate_does_not_use_unrelated_richer_pinout(self):
        source_payload = [
            {
                "source": "data-sheets/ICL8038.pdf",
                "displayName": "ICL8038.pdf",
                "pages": [1],
                "chunkCount": 3,
                "chunks": [],
            }
        ]
        intelligence = {
            "training/data-sheets/ICL8038.pdf": {
                "source": "training/data-sheets/ICL8038.pdf",
                "displayName": "ICL8038.pdf",
                "componentName": "ICL8038",
                "componentType": "waveform generator",
                "summary": "Waveform generator.",
                "confidence": 0.93,
                "facts": [],
                "pinout": {"pins": [{"pin": 1, "label": "SINE", "function": "Sine wave output", "page": 3}]},
            },
            "training/data-sheets/WEO012864MX.pdf": {
                "source": "training/data-sheets/WEO012864MX.pdf",
                "displayName": "WEO012864MX.pdf",
                "componentName": "WEO012864MX",
                "componentType": "microcontroller",
                "summary": "OLED module controller.",
                "confidence": 0.98,
                "facts": [{"type": "voltage", "label": "SUPPLY VOLTAGE", "value": "4", "unit": "V"}],
                "pinout": {
                    "pins": [
                        {"pin": index, "label": f"P{index}", "function": f"GPIO {index}", "page": 4}
                        for index in range(1, 17)
                    ]
                },
            },
        }

        card = build_circuit_build_card(
            "Create a Bench assembly plan from this Project Finder candidate: Rendered Page OCR.\n"
            "Source: data-sheets/ICL8038.pdf, page 1.\n"
            "Evidence summary: intersil ICL8038 Precision Waveform Generator.",
            source_payload,
            intelligence,
        )

        self.assertIsNone(card)

    def test_explicit_component_match_can_use_off_source_intelligence(self):
        source_payload = [
            {
                "source": "data-sheets/ICL8038.pdf",
                "displayName": "ICL8038.pdf",
                "pages": [1],
                "chunkCount": 3,
                "chunks": [],
            }
        ]
        intelligence = {
            "training/data-sheets/ICL8038.pdf": {
                "source": "training/data-sheets/ICL8038.pdf",
                "displayName": "ICL8038.pdf",
                "componentName": "ICL8038",
                "componentType": "waveform generator",
                "summary": "Waveform generator.",
                "confidence": 0.93,
                "facts": [],
                "pinout": {"pins": [{"pin": 1, "label": "SINE", "function": "Sine wave output", "page": 3}]},
            },
            "training/data-sheets/WEO012864MX.pdf": {
                "source": "training/data-sheets/WEO012864MX.pdf",
                "displayName": "WEO012864MX.pdf",
                "componentName": "WEO012864MX",
                "componentType": "display module",
                "summary": "OLED module.",
                "confidence": 0.98,
                "facts": [],
                "pinout": {
                    "pins": [
                        {"pin": 1, "label": "GND", "function": "GND", "page": 4},
                        {"pin": 2, "label": "VDD", "function": "VDD", "page": 4},
                    ]
                },
            },
        }

        card = build_circuit_build_card(
            "Create a build card for WEO012864MX.",
            source_payload,
            intelligence,
        )

        self.assertIsNotNone(card)
        self.assertEqual(card["componentName"], "WEO012864MX")
        self.assertEqual(card["sourceNotes"], [])


if __name__ == "__main__":
    unittest.main()
