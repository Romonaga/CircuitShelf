import unittest

from db.response_cache_store import PostgresResponseCache


class PostgresResponseCacheHelperTests(unittest.TestCase):
    def test_flattens_and_groups_source_payload(self):
        cache = PostgresResponseCache(None)
        flat = cache._flatten_sources([
            {
                "source": "training/ne555.pdf",
                "chunks": [
                    {
                        "index": 12,
                        "page": 3,
                        "section": "Pinout",
                        "category": "Reference",
                        "distance": 0.42,
                        "sourceImageId": "ne555.pdf_page3_img1",
                        "preview": "pinout table",
                    }
                ],
            }
        ])

        self.assertEqual(flat[0]["source"], "training/ne555.pdf")
        self.assertEqual(flat[0]["section"], "Pinout")

        rows = [
            {
                "source_path": "training/ne555.pdf",
                "page_number": 3,
                "distance": 0.42,
                "preview": "pinout table",
                "chunk_index": 12,
                "section_title": "Pinout",
                "category": "Reference",
                "source_image_key": "ne555.pdf_page3_img1",
            }
        ]
        grouped = cache._group_sources(rows)

        self.assertEqual(grouped[0]["displayName"], "ne555.pdf")
        self.assertEqual(grouped[0]["pages"], [3])
        self.assertEqual(grouped[0]["chunks"][0]["sourceImageId"], "ne555.pdf_page3_img1")


if __name__ == "__main__":
    unittest.main()
