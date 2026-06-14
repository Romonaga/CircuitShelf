from __future__ import annotations

from typing import Any

from backend.services.openai_assist_tasks import OpenAIAssistTaskRunner


class OpenAIAssistService:
    def __init__(self, ai_provider_store: Any, logger: Any = None, *, timeout_seconds: int = 90):
        self.tasks = OpenAIAssistTaskRunner(ai_provider_store, logger, timeout_seconds=timeout_seconds)

    def finalize_response(self, **kwargs):
        return self.tasks.finalize_response(**kwargs)

    def answer_without_sources(self, **kwargs):
        return self.tasks.answer_without_sources(**kwargs)

    def review_ingestion(self, **kwargs):
        return self.tasks.review_ingestion(**kwargs)

    def repair_datasheet_intelligence(self, **kwargs):
        return self.tasks.repair_datasheet_intelligence(**kwargs)

    def identify_inventory_photo(self, **kwargs):
        return self.tasks.identify_inventory_photo(**kwargs)

    def verify_bench_photo(self, **kwargs):
        return self.tasks.verify_bench_photo(**kwargs)

    def triage_project_finder(self, **kwargs):
        return self.tasks.triage_project_finder(**kwargs)

    def enrich_circuit_graph(self, **kwargs):
        return self.tasks.enrich_circuit_graph(**kwargs)

    def synthesize_conversation_bench_plan(self, **kwargs):
        return self.tasks.synthesize_conversation_bench_plan(**kwargs)
