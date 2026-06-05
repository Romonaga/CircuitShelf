from __future__ import annotations

from collections import deque

from backend.services.answer_markdown import normalize_answer_markdown
from backend.services.response_cache import ResponseCacheKey


class QueryTimingTracker:
    def __init__(self, *, maxlen: int = 100):
        self._timings = deque(maxlen=maxlen)

    def add(self, elapsed_seconds: float) -> None:
        self._timings.append(elapsed_seconds)

    def average_label(self) -> str:
        if not self._timings:
            return "N/A"
        avg_time = sum(self._timings) / len(self._timings)
        return f"{avg_time:.2f} sec over {len(self._timings)} queries"


def assemble_final_markdown(response: str, image_blocks: list[str]) -> str:
    answer_md = f"🧠 Answer\n\n{normalize_answer_markdown(response)}"
    image_md = "🖼️ Related Images\n\n" + "\n\n".join(image_blocks) if image_blocks else ""
    return f"{answer_md}\n\n---\n\n{image_md}" if image_md else answer_md


def build_response_cache_key(
    *,
    vector_store,
    entity_id=None,
    model_name,
    strategy,
    norm_q,
    retrieval_q,
    top_k,
    dist_thresh,
    max_tokens,
    show_full_text,
) -> ResponseCacheKey:
    return ResponseCacheKey(
        entity_id=int(entity_id) if entity_id is not None else None,
        index_fingerprint=vector_store.catalog_fingerprint(entity_id=entity_id),
        model=model_name or "",
        strategy=strategy,
        question=norm_q,
        retrieval_query=retrieval_q,
        top_k=int(top_k),
        distance_threshold=round(float(dist_thresh), 6),
        max_tokens=int(max_tokens or 0),
        show_full_text=bool(show_full_text),
    )
