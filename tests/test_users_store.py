import unittest

from db.users import UserStore


class UserStoreTests(unittest.TestCase):
    def test_token_hash_is_stable_and_does_not_echo_token(self):
        token = "example-token"

        first = UserStore._token_hash(token)
        second = UserStore._token_hash(token)

        self.assertEqual(first, second)
        self.assertNotEqual(first, token)
        self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
