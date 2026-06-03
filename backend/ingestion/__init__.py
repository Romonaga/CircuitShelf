"""CircuitShelf ingestion package.

Keep this module lightweight. Classifiers and models are used by tests and
review/intelligence code that should not import every parser dependency.
"""

from typing import Any

__all__ = ["IngestionPipeline"]


def __getattr__(name: str) -> Any:
    if name == "IngestionPipeline":
        from backend.ingestion.pipeline import IngestionPipeline

        return IngestionPipeline
    raise AttributeError(name)
