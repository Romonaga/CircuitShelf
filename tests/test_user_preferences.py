import unittest

from db.user_preferences import UserPreferencesStore


class UserPreferencesStoreTests(unittest.TestCase):
    def test_get_without_user_returns_default(self):
        store = UserPreferencesStore(None)

        self.assertEqual(store.get(None, "ask.retrieval", {"bypassCache": True}), {"bypassCache": True})


if __name__ == "__main__":
    unittest.main()
