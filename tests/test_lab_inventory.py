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

        self.assertEqual(missing[0]["name"], "LED")
        self.assertEqual(missing[0]["type"], "indicator")
        self.assertIn("not found", missing[0]["reason"])

    def test_required_parts_report_alias_substitutions(self):
        store = ProjectFinderStore(None, None)
        inventory_index = {
            key: {"id": "1", "displayName": "LM555", "partType": "timer", "quantity": 10}
            for key in part_lookup_keys("LM555", "timer")
        }

        resolution = store._resolve_required_parts(
            [{"name": "NE555 timer", "type": "timer"}],
            inventory_index,
        )

        self.assertEqual(resolution["missingParts"], [])
        self.assertEqual(resolution["matchedParts"][0]["displayName"], "LM555")
        self.assertEqual(resolution["suggestedSubstitutions"][0]["required"], "NE555 timer")
        self.assertEqual(resolution["suggestedSubstitutions"][0]["use"], "LM555")

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
        self.assertEqual(deduped[0]["dedupeCount"], 2)

    def test_rejects_low_value_non_project_candidates(self):
        store = ProjectFinderStore(None, None)

        project_like, reasons = store._project_qualification(
            "Parts for Fig. 5.3 copyright publisher website email.",
            "Project 5.3 Parts for Fig.",
            [{"name": "LED", "type": "indicator"}],
            [],
        )

        self.assertFalse(project_like)
        self.assertTrue(reasons)

    def test_accepts_code_sample_evidence_as_project_candidate(self):
        store = ProjectFinderStore(None, None)

        project_like, reasons = store._project_qualification(
            "Code sample pack: blink\nComponents: LED\nvoid setup(){ pinMode(13, OUTPUT); }\nvoid loop(){ digitalWrite(13, HIGH); }",
            "Code sample: blink",
            [{"name": "LED", "type": "indicator"}],
            [{"id": "1", "displayName": "LED", "partType": "indicator", "quantity": 10}],
        )

        self.assertTrue(project_like)
        self.assertEqual(reasons, [])

    def test_candidate_title_skips_low_value_ocr_headings(self):
        store = ProjectFinderStore(None, None)

        title = store._candidate_title(
            "Make - Electronics.pdf",
            "Image OCR",
            [{"name": "NE555 timer", "type": "timer"}],
            [],
        )

        self.assertEqual(title, "NE555 timer circuit from Make - Electronics.pdf")

    def test_chunk_candidate_uses_inventory_aliases_in_objective(self):
        store = ProjectFinderStore(None, None)
        inventory_index = {
            key: {"id": "1", "displayName": "LM555", "partType": "timer", "quantity": 10}
            for key in part_lookup_keys("LM555", "timer")
        }
        inventory_index.update(
            {
                key: {"id": "2", "displayName": "Red LED", "partType": "indicator", "quantity": 50}
                for key in part_lookup_keys("Red LED", "indicator")
            }
        )

        candidate = store._chunk_candidate(
            {
                "chunk_text": "Build a 555 timer LED flasher on a breadboard. Wire the 555 output to the LED.",
                "matched_terms": ["lm555", "red led"],
                "matched_count": 2,
                "quality_score": 1,
                "section_title": "555 LED flasher",
                "display_name": "book.pdf",
                "source_path": "book.pdf",
                "page_number": 12,
                "chunk_index": 4,
            },
            inventory_index,
        )

        self.assertTrue(candidate["projectLike"])
        self.assertIn("NE555 timer -> LM555", candidate["objective"])
        self.assertIn("Breadboard", {part["name"] for part in candidate["missingParts"]})

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
