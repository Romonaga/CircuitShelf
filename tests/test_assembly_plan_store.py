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


if __name__ == "__main__":
    unittest.main()
