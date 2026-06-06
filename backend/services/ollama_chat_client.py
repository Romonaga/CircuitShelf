import requests
import time
import threading
from requests.exceptions import RequestException

from backend.services.conversation_manager import build_chat_messages


class LocalLlmRequestGate:
    def __init__(self, *, max_concurrent: int = 1, queue_timeout_seconds: float = 300):
        self._condition = threading.Condition()
        self._max_concurrent = max(1, int(max_concurrent or 1))
        self._queue_timeout_seconds = max(0.0, float(queue_timeout_seconds or 0))
        self._active = 0
        self._waiting = 0
        self._completed = 0
        self._timed_out = 0
        self._last_wait_seconds = 0.0

    def configure(self, *, max_concurrent: int | None = None, queue_timeout_seconds: float | None = None) -> None:
        with self._condition:
            if max_concurrent is not None:
                self._max_concurrent = max(1, int(max_concurrent or 1))
            if queue_timeout_seconds is not None:
                self._queue_timeout_seconds = max(0.0, float(queue_timeout_seconds or 0))
            self._condition.notify_all()

    def acquire(self) -> float | None:
        started = time.monotonic()
        timeout = self._queue_timeout_seconds or None
        with self._condition:
            self._waiting += 1
            try:
                while self._active >= self._max_concurrent:
                    if timeout is None:
                        self._condition.wait()
                        continue
                    remaining = timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        self._timed_out += 1
                        return None
                    self._condition.wait(remaining)
                self._active += 1
                waited = time.monotonic() - started
                self._last_wait_seconds = waited
                return waited
            finally:
                self._waiting = max(0, self._waiting - 1)

    def release(self) -> None:
        with self._condition:
            self._active = max(0, self._active - 1)
            self._completed += 1
            self._condition.notify()

    def status(self) -> dict:
        with self._condition:
            return {
                "maxConcurrent": self._max_concurrent,
                "queueTimeoutSeconds": self._queue_timeout_seconds,
                "active": self._active,
                "waiting": self._waiting,
                "completed": self._completed,
                "timedOut": self._timed_out,
                "lastWaitSeconds": round(self._last_wait_seconds, 3),
            }


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
        max_concurrent_requests: int = 1,
        queue_timeout_seconds: float = 300,
        keep_alive: str | int | None = "30s",
        gpu_coordinator=None,
        gpu_priority: int = 10,
        gpu_owner: str = "web",
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
        self.keep_alive = keep_alive
        self.gpu_coordinator = gpu_coordinator
        self.gpu_priority = int(gpu_priority)
        self.gpu_owner = gpu_owner
        self.request_gate = LocalLlmRequestGate(
            max_concurrent=max_concurrent_requests,
            queue_timeout_seconds=queue_timeout_seconds,
        )

    def configure_runtime(
        self,
        *,
        max_concurrent_requests: int | None = None,
        queue_timeout_seconds: float | None = None,
        keep_alive: str | int | None = None,
    ) -> None:
        self.request_gate.configure(
            max_concurrent=max_concurrent_requests,
            queue_timeout_seconds=queue_timeout_seconds,
        )
        if keep_alive is not None:
            self.keep_alive = keep_alive

    def status(self) -> dict:
        return {
            **self.request_gate.status(),
            "keepAlive": self.keep_alive,
            "coordinatedByLocalGpuQueue": bool(self.gpu_coordinator),
        }

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
        if self.keep_alive not in (None, ""):
            payload["keep_alive"] = self.keep_alive

        if self.gpu_coordinator:
            try:
                with self.gpu_coordinator.lease(
                    task_type="local_llm",
                    priority=self.gpu_priority,
                    owner=self.gpu_owner,
                    details={"model": model_name or "default"},
                    timeout_seconds=self.request_gate.status()["queueTimeoutSeconds"],
                ):
                    return self._post_chat_with_retry(url, headers, payload, retries, delay)
            except TimeoutError:
                timeout = self.request_gate.status()["queueTimeoutSeconds"]
                self.trace_logger.warning(f"⚠️ Local GPU queue timed out local LLM after {timeout:.1f}s.")
                return f"[LLM busy: local GPU queue timed out after {timeout:.0f}s]"

        waited = self.request_gate.acquire()
        if waited is None:
            timeout = self.request_gate.status()["queueTimeoutSeconds"]
            self.trace_logger.warning(f"⚠️ Local LLM queue timed out after {timeout:.1f}s.")
            return f"[LLM busy: local model queue timed out after {timeout:.0f}s]"
        if waited > 0.25:
            self.trace_logger.info(f"⏳ Local LLM request waited {waited:.2f}s for the GPU/model queue.")

        try:
            return self._post_chat_with_retry(url, headers, payload, retries, delay)
        finally:
            self.request_gate.release()

    def _post_chat_with_retry(self, url, headers, payload, retries, delay):
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
