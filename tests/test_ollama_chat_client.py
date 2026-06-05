import threading
import time

from backend.services.ollama_chat_client import OllamaChatClient


class DummyConfig:
    def get(self, key, default=None):
        return default


class DummyLogger:
    def __init__(self):
        self.messages = []

    def debug(self, message):
        self.messages.append(("debug", message))

    def info(self, message):
        self.messages.append(("info", message))

    def warning(self, message):
        self.messages.append(("warning", message))


class DummyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": "queued answer"}}


def make_client(**overrides):
    values = {
        "config": DummyConfig(),
        "trace_logger": DummyLogger(),
        "api_url": "http://ollama.example/api",
        "default_system_prompt": "system",
        "default_temperature": 0.2,
        "default_num_predict": 128,
        "default_num_ctx": 2048,
        "post_timeout": 5,
        "query_retries": 1,
        "query_retry_delay": 0,
        "max_chat_history_turns": 2,
        "max_chat_history_chars": 500,
    }
    values.update(overrides)
    return OllamaChatClient(**values)


def test_ollama_payload_includes_keep_alive(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr("backend.services.ollama_chat_client.requests.post", fake_post)
    client = make_client(keep_alive="0")

    result = client.chat_with_retry("question", "model-a")

    assert result == "queued answer"
    assert captured["url"] == "http://ollama.example/api/chat"
    assert captured["json"]["keep_alive"] == "0"
    assert captured["json"]["model"] == "model-a"
    assert captured["timeout"] == 5


def test_local_llm_queue_timeout_prevents_second_request(monkeypatch):
    calls = 0
    release_first_request = threading.Event()

    def slow_post(url, headers, json, timeout):
        nonlocal calls
        calls += 1
        release_first_request.wait(timeout=1)
        return DummyResponse()

    monkeypatch.setattr("backend.services.ollama_chat_client.requests.post", slow_post)
    client = make_client(max_concurrent_requests=1, queue_timeout_seconds=0.02)

    first = threading.Thread(target=lambda: client.chat_with_retry("first", "model-a"))
    first.start()
    time.sleep(0.05)

    result = client.chat_with_retry("second", "model-a")
    release_first_request.set()
    first.join(timeout=1)

    assert "LLM busy" in result
    assert calls == 1
    assert client.status()["timedOut"] == 1


def test_runtime_queue_configuration_changes_status():
    client = make_client(max_concurrent_requests=1, queue_timeout_seconds=300, keep_alive="30s")

    client.configure_runtime(max_concurrent_requests=3, queue_timeout_seconds=15, keep_alive="5s")

    status = client.status()
    assert status["maxConcurrent"] == 3
    assert status["queueTimeoutSeconds"] == 15
    assert status["keepAlive"] == "5s"
