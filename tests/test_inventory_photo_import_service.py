import unittest

from backend.services.inventory_photo_import_service import InventoryPhotoImportService


class FakeOpenAIAssist:
    def identify_inventory_photo(self, **_kwargs):
        return {
            "items": [
                {
                    "displayName": "Red LED",
                    "partType": "diode",
                    "quantity": 25,
                    "aliases": ["red led", "indicator led"],
                    "notes": "Drawer label says red.",
                    "confidence": 0.92,
                    "warnings": [],
                },
                {
                    "displayName": "NE555 timer IC",
                    "partType": "ic",
                    "quantity": 5,
                    "aliases": ["555 timer", "LM555"],
                    "notes": "",
                    "confidence": 0.88,
                    "warnings": [],
                },
            ],
            "model": "gpt-test",
            "paidBy": "user",
            "estimatedCost": 0.0123,
        }


class InventoryPhotoImportServiceTests(unittest.TestCase):
    def test_photo_preview_marks_existing_alias_match(self):
        service = InventoryPhotoImportService(FakeOpenAIAssist())
        result = service.preview(
            image_bytes=b"image",
            mime_type="image/png",
            note="drawer 1",
            entity_id=1,
            user_id=2,
            existing_parts=[
                {
                    "id": "part-555",
                    "displayName": "LM555 timers",
                    "aliases": ["555 timer"],
                }
            ],
        )

        items = {item["displayName"]: item for item in result["items"]}
        self.assertEqual(items["Red LED"]["action"], "create")
        self.assertEqual(items["NE555 timer IC"]["action"], "merge")
        self.assertEqual(items["NE555 timer IC"]["existingPartId"], "part-555")
        self.assertEqual(result["model"], "gpt-test")


if __name__ == "__main__":
    unittest.main()
