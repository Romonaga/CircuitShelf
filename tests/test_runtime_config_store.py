import unittest

from db.runtime_config_store import RuntimeConfigStore


class RuntimeConfigStoreTests(unittest.TestCase):
    def test_llm_seed_rows_use_default_model_first_class(self):
        rows = RuntimeConfigStore._llm_seed_rows(
            {
                "LLM_MODEL_NAME": "electronics-helper:latest",
                "LLM_MODEL_OPTIONS": ["general:latest", "electronics-helper:latest"],
                "LLM_TEMPERATURE": 0.1,
                "LLM_NUM_PREDICT": 2048,
                "LLM_NUM_CTX": 8192,
            }
        )

        self.assertEqual([row["model_name"] for row in rows], ["general:latest", "electronics-helper:latest"])
        default = [row for row in rows if row["is_default"]]
        self.assertEqual(len(default), 1)
        self.assertEqual(default[0]["model_name"], "electronics-helper:latest")
        self.assertEqual(default[0]["temperature"], 0.1)
        self.assertEqual(default[0]["num_predict"], 2048)
        self.assertEqual(default[0]["num_ctx"], 8192)

    def test_llm_seed_rows_add_missing_default(self):
        rows = RuntimeConfigStore._llm_seed_rows(
            {
                "LLM_MODEL_NAME": "electronics-helper:latest",
                "LLM_MODEL_OPTIONS": ["general:latest"],
            }
        )

        self.assertEqual(rows[0]["model_name"], "electronics-helper:latest")
        self.assertTrue(rows[0]["is_default"])

    def test_query_synonym_rows_ignore_invalid_entries(self):
        rows = RuntimeConfigStore._query_synonym_rows(
            [
                ["ground", "gnd"],
                ["power"],
                ["", "blank"],
                ("microcontroller", "mcu"),
            ]
        )

        self.assertEqual(rows, [("ground", "gnd"), ("microcontroller", "mcu")])


if __name__ == "__main__":
    unittest.main()
