import unittest

from backend.services.ingest_stats import collect_document_ingest_stats, count_state_pages_by_document


class FakeState:
    def __init__(self):
        self.sources = ["training/timer.pdf", "training/timer.pdf", "training/timer.pdf"]
        self.metadata = [
            {"source": "training/timer.pdf", "page": 1},
            {"source": "training/timer.pdf", "page": 4},
            {"source": "training/timer.pdf", "page": 2},
        ]
        self.image_ids = ["timer.pdf_page4_img1"]
        self.image_text = {"timer.pdf_page4_img1": "pinout diagram text"}
        self.image_store = {"timer.pdf_page4_img1": "base64"}

    def get_sources(self):
        return list(self.sources)

    def get_metadata(self):
        return list(self.metadata)

    def get_image_id_list(self):
        return list(self.image_ids)

    def get_image_page_text(self):
        return dict(self.image_text)

    def get_image_store(self):
        return dict(self.image_store)


class FakeVectorStore:
    @staticmethod
    def rel_path_for_source(source, _meta):
        return source.removeprefix("training/")


class IngestStatsTests(unittest.TestCase):
    def test_page_count_uses_highest_page_seen_for_document(self):
        state = FakeState()

        counts = count_state_pages_by_document(state, vector_store=FakeVectorStore())

        self.assertEqual(counts, {"timer.pdf": 4})

    def test_collect_document_stats_includes_page_count(self):
        state = FakeState()

        stats = collect_document_ingest_stats(
            state,
            ["timer.pdf"],
            vector_store=FakeVectorStore(),
            image_asset_belongs_to_document=lambda image_id, rel_path: image_id.startswith(rel_path),
        )

        self.assertEqual(stats["timer.pdf"]["pageCount"], 4)


if __name__ == "__main__":
    unittest.main()
