import unittest

from settings_runtime import RuntimeSettingsManager, setting_restart_required


class ConfigStub:
    def __init__(self, values):
        self.config = dict(values)


class RuntimeSettingsManagerTests(unittest.TestCase):
    def test_applies_live_setting_to_config_and_module_globals(self):
        config = ConfigStub({"PDF_RENDER_MAX_PAGES_PER_DOC": 8})
        module_globals = {"PDF_RENDER_MAX_PAGES_PER_DOC": 8}
        manager = RuntimeSettingsManager(config, module_globals)

        change = manager.apply_update("PDF_RENDER_MAX_PAGES_PER_DOC", 20)

        self.assertTrue(change.changed)
        self.assertTrue(change.runtime_applied)
        self.assertFalse(change.restart_required)
        self.assertEqual(config.config["PDF_RENDER_MAX_PAGES_PER_DOC"], 20)
        self.assertEqual(module_globals["PDF_RENDER_MAX_PAGES_PER_DOC"], 20)

    def test_startup_setting_updates_config_but_not_live_global(self):
        config = ConfigStub({"EMBED_MODEL_NAME": "old-model"})
        module_globals = {"EMBED_MODEL_NAME": "old-model"}
        manager = RuntimeSettingsManager(config, module_globals)

        change = manager.apply_update("EMBED_MODEL_NAME", "new-model")

        self.assertTrue(change.changed)
        self.assertFalse(change.runtime_applied)
        self.assertTrue(change.restart_required)
        self.assertEqual(config.config["EMBED_MODEL_NAME"], "new-model")
        self.assertEqual(module_globals["EMBED_MODEL_NAME"], "old-model")

    def test_callback_receives_live_setting_change(self):
        config = ConfigStub({"RERANK_PROFILES": "old"})
        received = []
        manager = RuntimeSettingsManager(config, {})
        manager.register_callback("RERANK_PROFILES", received.append)

        change = manager.apply_update("RERANK_PROFILES", "new")

        self.assertTrue(change.runtime_applied)
        self.assertEqual(received, ["new"])

    def test_apply_updates_reports_only_changed_values(self):
        config = ConfigStub({"A": 1, "B": 2})
        manager = RuntimeSettingsManager(config, {})

        changes = manager.apply_updates({"A": 1, "B": 3})

        self.assertEqual([change.key for change in changes], ["B"])
        self.assertEqual(config.config["B"], 3)

    def test_restart_required_catalog_marks_known_startup_settings(self):
        self.assertTrue(setting_restart_required("APP_PORT"))
        self.assertTrue(setting_restart_required("CROSS_ENCODER_MODEL"))
        self.assertFalse(setting_restart_required("PDF_RENDER_MAX_PAGES_PER_DOC"))
        self.assertFalse(setting_restart_required("LLM_NUM_PREDICT"))


if __name__ == "__main__":
    unittest.main()
