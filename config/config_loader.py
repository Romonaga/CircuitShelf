#config/config_loader.py
import os
import yaml



class Config:
    REQUIRED_KEYS = [
        "EMBED_MODEL_NAME", "CROSS_ENCODER_MODEL",
        "LLM_MODEL_NAME", "LLM_MODEL_OPTIONS", "OLLAMA_API_URL",
        "TRAINING_DIR", "BUILD_INDEX_LOG_FILE",
        "DOC_EXT", "PDF_EXT", "MD_EXT", "IMG_EXTENSIONS",
        "CHUNK_SIZE", "CHUNK_OVERLAP", "SPECIAL_SECTION_PRIORITY",
        "TRACE_LOG_FILE", "PROMPT_DIR"
    ]

    def __init__(self, config_path, trace_logger):
        self.trace_logger = trace_logger
        self.config_path = config_path
        self.config = self._load_config()
        self.validate_required_keys()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            self.trace_logger.critical(f"❌ Config file not found at: {self.config_path}")
            exit(1)
        with open(self.config_path, "r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    raise ValueError("Config content is not a valid dictionary.")
                return data
            except Exception as e:
                self.trace_logger.critical(f"❌ Failed to parse config file: {e}")
                exit(1)

    def __getitem__(self, key):
        if key not in self.config:
            self.trace_logger.critical(f"❌ Missing required config key: '{key}'")
            exit(1)
        return self.config[key]

    def __contains__(self, key):
        return key in self.config

    def get(self, key, default=None):
        return self.config.get(key, default)

    def validate_required_keys(self):
        missing = [k for k in self.REQUIRED_KEYS if k not in self.config]
        if missing:
            for key in missing:
                self.trace_logger.critical(f"❌ Missing required config key: '{key}'")
            exit(1)

    def validate_rerank_profiles(self, profiles):
        unused = [name for name, data in profiles.items() if name != "default" and not data.get("keywords")]
        if unused:
            self.trace_logger.warning(f"⚠️ RERANK_PROFILES missing keywords: {unused}")
        if "default" not in profiles:
            self.trace_logger.error("❌ Missing required 'default' profile in RERANK_PROFILES.")
            exit(1)
