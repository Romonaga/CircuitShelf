import requests
import time
from requests.exceptions import RequestException

from backend.services.conversation_manager import build_chat_messages


class OllamaChatClient:
    def __init__(
        self,
        *,
        config,
        trace_logger,
        api_url: str,
        default_system_prompt: str,
        default_temperature: float,
        default_num_predict: int,
        default_num_ctx,
        post_timeout: int,
        query_retries: int,
        query_retry_delay: float,
        max_chat_history_turns: int,
        max_chat_history_chars: int,
    ):
        self.config = config
        self.trace_logger = trace_logger
        self.api_url = api_url
        self.default_system_prompt = default_system_prompt
        self.default_temperature = default_temperature
        self.default_num_predict = default_num_predict
        self.default_num_ctx = default_num_ctx
        self.post_timeout = post_timeout
        self.query_retries = query_retries
        self.query_retry_delay = query_retry_delay
        self.max_chat_history_turns = max_chat_history_turns
        self.max_chat_history_chars = max_chat_history_chars

    def chat_with_retry(self, prompt, model_name, chat_history=None, retries=None, delay=None, system_prompt=None):
        retries = int(self.query_retries if retries is None else retries)
        delay = float(self.query_retry_delay if delay is None else delay)

        llm_api_key = self.config.get("LLM_API_KEY", "")
        url = f"{self.api_url}/chat"

        headers = {
            "Content-Type": "application/json"
        }
        if llm_api_key:
            headers["Authorization"] = f"Bearer {llm_api_key}"

        options = {
            "temperature": float(self.default_temperature),
            "num_predict": int(self.default_num_predict),
        }
        if self.default_num_ctx:
            options["num_ctx"] = int(self.default_num_ctx)

        payload = {
            "model": model_name or "default",
            "stream": False,
            "messages": build_chat_messages(
                system_prompt or self.default_system_prompt,
                prompt,
                chat_history,
                max_turns=self.max_chat_history_turns,
                max_chars=self.max_chat_history_chars,
            ),
            "options": options,
        }

        for attempt in range(retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=self.post_timeout)
                response.raise_for_status()

                json_data = response.json()
                result = json_data.get("message", {}).get("content", "").strip()
                done_reason = json_data.get("done_reason", "")
                if done_reason in {"length", "max_tokens"}:
                    self.trace_logger.warning(
                        "⚠️ Ollama response stopped at generation limit. "
                        f"Increase LLM_NUM_PREDICT above {self.default_num_predict} if this answer needs more room."
                    )
                    result = (
                        f"{result}\n\n"
                        "> Response stopped at the model generation limit. "
                        "Increase the answer token limit and ask again if this is incomplete."
                    )

                self.trace_logger.debug(f"✅ LLM call success: {result[:80]}...")
                return result

            except RequestException as exc:
                self.trace_logger.warning(f"⚠️ LLM call failed (attempt {attempt + 1}/{retries}) | {exc}")
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    return "[LLM error]"
