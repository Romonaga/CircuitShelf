import unittest

from db.lab_inventory import ProjectFinderStore, infer_required_parts, normalize_part_name, part_lookup_keys


class LabInventoryTests(unittest.TestCase):
    def test_normalizes_common_part_names(self):
        self.assertEqual(normalize_part_name("10 kΩ Resistor"), "10 kohm resistor")
        self.assertEqual(normalize_part_name("NE-555 Timer"), "ne 555 timer")

    def test_infers_required_parts_from_project_text(self):
        parts = infer_required_parts(
            "Build a 555 timer LED flasher on a breadboard with a 10 kΩ resistor and 10 uF capacitor."
        )
        names = {part["name"] for part in parts}

        self.assertIn("NE555 timer", names)
        self.assertIn("LED", names)
        self.assertIn("Breadboard", names)
        self.assertIn("10 k ohm resistor", names)
        self.assertIn("10 uF capacitor", names)

    def test_common_part_lookup_keys_match_variants(self):
        keys = set(part_lookup_keys("LM555", "timer"))
        self.assertIn("555 timer", keys)
        self.assertIn("ne555", keys)
        self.assertIn("lm555", keys)

    def test_missing_parts_use_inventory_alias_families(self):
        store = ProjectFinderStore(None, None)
        inventory_index = {
            key: {"id": "1", "displayName": "LM555", "partType": "timer", "quantity": 10}
            for key in part_lookup_keys("LM555", "timer")
        }
        missing = store._missing_parts(
            [
                {"name": "NE555 timer", "type": "timer"},
                {"name": "LED", "type": "indicator"},
            ],
            inventory_index,
        )

        self.assertEqual(missing, [{"name": "LED", "type": "indicator"}])

    def test_dedupe_candidates_collapses_same_source_and_required_parts(self):
        store = ProjectFinderStore(None, None)
        candidates = [
            {
                "id": "a",
                "kind": "project_chunk",
                "source": "book.pdf",
                "title": "Image OCR",
                "summary": "555 timer flasher",
                "requiredParts": [{"name": "NE555 timer", "type": "timer"}],
                "projectLike": True,
                "score": 12,
            },
            {
                "id": "b",
                "kind": "project_chunk",
                "source": "book.pdf",
                "title": "Image OCR",
                "summary": "same OCR fragment",
                "requiredParts": [{"name": "NE555 timer", "type": "timer"}],
                "projectLike": True,
                "score": 30,
            },
        ]

        deduped = store._dedupe_candidates(candidates)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["id"], "b")

    def test_missing_part_summary_ranks_repeated_gaps(self):
        store = ProjectFinderStore(None, None)
        summary = store._missing_part_summary(
            [
                {
                    "title": "LED flasher",
                    "missingParts": [
                        {"name": "Breadboard", "type": "tooling"},
                        {"name": "10 uF capacitor", "type": "capacitor"},
                    ],
                },
                {
                    "title": "Timer alarm",
                    "missingParts": [
                        {"name": "Breadboard", "type": "tooling"},
                    ],
                },
            ]
        )

        self.assertEqual(summary[0]["name"], "Breadboard")
        self.assertEqual(summary[0]["count"], 2)
        self.assertEqual(summary[0]["exampleTitles"], ["LED flasher", "Timer alarm"])


if __name__ == "__main__":
    unittest.main()
