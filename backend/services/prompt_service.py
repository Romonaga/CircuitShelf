import os
from typing import Callable


class PromptService:
    def __init__(
        self,
        *,
        config,
        prompt_dir: str,
        trace_logger,
        token_length: Callable[[str], int],
    ):
        self.config = config
        self.prompt_dir = prompt_dir
        self.trace_logger = trace_logger
        self.token_length = token_length

    def load_prompt_template(self, path: str, context: str, question: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as prompt_file:
                template = prompt_file.read()
            return template.format(context=context, question=question)
        except Exception as exc:
            self.trace_logger.error(f"❌ Failed to load prompt template {path}: {exc}")
            return f"[Prompt load error: {exc}]"

    def build_prompt(self, context: str, question: str, is_math: bool = False) -> str:
        db_template_key = "PROMPT_TEMPLATE_MATH" if is_math else "PROMPT_TEMPLATE_GENERAL"
        db_template = self.config.get(db_template_key)
        if db_template:
            try:
                return db_template.format(context=context, question=question)
            except Exception as exc:
                self.trace_logger.error(f"❌ Failed to format DB prompt template {db_template_key}: {exc}")

        prompt_file = os.path.join(self.prompt_dir, "math_prompt.txt" if is_math else "general_prompt.txt")
        return self.load_prompt_template(prompt_file, context, question)

    def trim_chunks_to_token_budget(self, selected_chunks: list[dict], max_tokens: int | None) -> list[dict]:
        if not max_tokens:
            return selected_chunks

        trimmed = []
        token_total = 0
        for chunk in selected_chunks:
            chunk_tokens = self.token_length(chunk.get("text", ""))
            if trimmed and token_total + chunk_tokens > max_tokens:
                break
            trimmed.append(chunk)
            token_total += chunk_tokens

        return trimmed
