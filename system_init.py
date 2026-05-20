import os
import time
import logging
import yaml
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

CONFIG_PATH = os.path.join("config", "config.yaml")
class ConfigWrapper:
    def __init__(self, config_dict):
        self.config = config_dict

    def __getitem__(self, key):
        if key not in self.config:
            raise KeyError(f"Missing required config key: '{key}'")
        return self.config[key]

    def __contains__(self, key):
        return key in self.config

    def get(self, key, default=None):
        return self.config.get(key, default)

    def validate_required_keys(self, required_keys):
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {missing}")

    def validate_rerank_profiles(self, profiles):
        unused = [name for name, data in profiles.items() if not data.get("keywords")]
        if unused:
            print(f"⚠️ RERANK_PROFILES missing keywords: {unused}")
        if "default" not in profiles:
            raise ValueError("❌ Missing required 'default' profile in RERANK_PROFILES.")

class EmojiFormatter(logging.Formatter):
    LEVEL_ICONS = {
        logging.DEBUG: "🐛 DEBUG",
        logging.INFO: "ℹ️ INFO",
        logging.WARNING: "⚠️ WARNING",
        logging.ERROR: "❌ ERROR",
        logging.CRITICAL: "🔥 CRITICAL"
    }

    def format(self, record):
        icon = self.LEVEL_ICONS.get(record.levelno, "❓")
        record.levelname = icon
        return super().format(record)


class SystemInit:
    def __init__(
        self,
        name="trace_logger",
        level=logging.DEBUG,
        logfile="logs/trace.log",
        rotate="size",  # "size" or "time"
        max_bytes=5 * 1024 * 1024,
        backup_count=7,
        when="midnight",
        interval=1,
        use_timestamped_name=False
    ):
        self.name = name
        self.level = level
        self.logfile = logfile
        self.rotate = rotate
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.when = when
        self.interval = interval
        self.use_timestamped_name = use_timestamped_name
        self.logger = self._create_logger()

    def _create_logger(self):
        logfile = self.logfile
        if self.use_timestamped_name:
            base, ext = os.path.splitext(logfile)
            logfile = f"{base}_{time.strftime('%Y-%m-%d_%H-%M-%S')}{ext}"

        os.makedirs(os.path.dirname(logfile), exist_ok=True)

        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        logger.handlers.clear()

        formatter = EmojiFormatter("[%(asctime)s] %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")

        # Console handler
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # File handler
        if self.rotate == "time":
            file_handler = TimedRotatingFileHandler(
                logfile, when=self.when, interval=self.interval,
                backupCount=self.backup_count, encoding="utf-8"
            )
        else:
            file_handler = RotatingFileHandler(
                logfile, maxBytes=self.max_bytes,
                backupCount=self.backup_count, encoding="utf-8"
            )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.propagate = False
        return logger

    def get_logger(self):
        return self.logger

    @staticmethod
    def flush_logger(logger):
        for handler in logger.handlers:
            if hasattr(handler, 'flush'):
                try:
                    handler.flush()
                except Exception:
                    pass

    @staticmethod
    def log_build_info(logger, chunks=None, embeddings=None, image_ids=None, duration=None):
        chunks = chunks or []
        embeddings = embeddings or []
        image_ids = image_ids or []
        duration = duration or 0.0

        summary = (
            "==== Index Build Summary ====\n"
            f"  Time: {time.ctime()}\n"
            f"  ⏱️ Duration: {duration:.2f} sec\n"
            f"  📦 Chunks: {len(chunks)}\n"
            f"  🧠 Embeddings: {len(embeddings)}\n"
            f"  🖼️ Images Indexed: {len(image_ids)}\n"
        )
        logger.info(summary.strip())


    @staticmethod
    def load_config_and_logger():
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError(f"Config file not found at {CONFIG_PATH}")

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        logfile = config.get("TRACE_LOG_FILE", "logs/trace.log")
        rotate = config.get("TRACE_ROTATE", "time")
        max_bytes = config.get("TRACE_MAX_BYTES", 10485760)
        backup_count = config.get("TRACE_BACKUP_COUNT", 7)
        when = config.get("TRACE_WHEN", "midnight")
        use_timestamped = config.get("TRACE_TIMESTAMPED_NAME", True)
        log_level = config.get("TRACE_LOG_LEVEL", "DEBUG").upper()
        if log_level not in logging._nameToLevel:
            raise ValueError(f"Invalid log level: {log_level}")
        log_level = logging._nameToLevel[log_level]

        trace_logger = SystemInit(
            name="trace_logger",
            logfile=logfile,
            level=log_level,
            rotate=rotate,
            max_bytes=max_bytes,
            backup_count=backup_count,
            when=when,
            use_timestamped_name=use_timestamped
        )

        return ConfigWrapper(config), trace_logger.get_logger()

