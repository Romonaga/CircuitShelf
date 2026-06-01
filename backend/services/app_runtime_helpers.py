from typing import Any

import numpy as np


def sanitize_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return sanitize_for_json(value.tolist())
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def conversation_title_from_question(question: str) -> str:
    title = " ".join(str(question or "").split())
    if not title:
        return "New conversation"
    return title[:80]


class TraceLogHelper:
    def __init__(self, *, trace_logger, default_log_file: str):
        self.trace_logger = trace_logger
        self.default_log_file = default_log_file

    def flush(self) -> None:
        for handler in self.trace_logger.handlers:
            if hasattr(handler, "flush"):
                handler.flush()

    def current_file(self) -> str:
        for handler in self.trace_logger.handlers:
            base_filename = getattr(handler, "baseFilename", None)
            if base_filename:
                return base_filename
        return self.default_log_file
