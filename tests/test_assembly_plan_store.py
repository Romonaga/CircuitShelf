import unittest

from db.assembly_plan_store import AssemblyPlanStore


class AssemblyPlanStoreHelperTests(unittest.TestCase):
    def test_rel_path_for_source_removes_training_prefix(self):
        store = AssemblyPlanStore(None, "training")

        self.assertEqual(store.rel_path_for_source("training/ne555.pdf"), "ne555.pdf")
        self.assertEqual(store.rel_path_for_source("training/books/ne555.pdf"), "books/ne555.pdf")
        self.assertEqual(store.rel_path_for_source("ne556.pdf"), "ne556.pdf")

    def test_source_notes_normalize_pages_and_paths(self):
        store = AssemblyPlanStore(None, "training")

        sources = store._source_notes(
            [
                {
                    "source": "training/ne555.pdf",
                    "displayName": "NE555",
                    "pages": [1, "2", "bad", 2],
                    "chunks": 3,
                }
            ]
        )

        self.assertEqual(sources[0]["source_path"], "ne555.pdf")
        self.assertEqual(sources[0]["display_name"], "NE555")
        self.assertEqual(sources[0]["pages"], [1, 2])
        self.assertEqual(sources[0]["chunk_count"], 3)

    def test_photo_check_maps_step_verification_fields(self):
        store = AssemblyPlanStore(None, "training")

        row = {
            "id": "check-1",
            "plan_id": "plan-1",
            "step_id": "step-1",
            "user_id": 7,
            "image_mime_type": "image/png",
            "note": "step photo",
            "checklist": "manual checks",
            "diagnostics": {"width": 800},
            "verification_status": "needs_attention",
            "verification_confidence": 0.42,
            "verification_summary": "Photo is blurry.",
            "verification_findings": ["Retake photo"],
            "requested_evidence": ["Close-up"],
            "verification_provider": "ollama",
            "verification_model": "electronics-helper",
            "ai_result": {"status": "needs_attention"},
            "created_at": None,
        }

        check = store._photo_check(row)

        self.assertEqual(check["stepId"], "step-1")
        self.assertEqual(check["verification"]["status"], "needs_attention")
        self.assertEqual(check["verification"]["confidence"], 0.42)
        self.assertEqual(check["verification"]["requestedEvidence"], ["Close-up"])


if __name__ == "__main__":
    unittest.main()
