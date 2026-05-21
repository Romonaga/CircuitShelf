import re
from dataclasses import dataclass
from html import unescape
from typing import Any, Iterable


_TAG_RE = re.compile(r"<[^>]+>")
_DATA_IMAGE_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']data:image/[^\"']+[\"'][^>]*>", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ChatTurn:
    question: str
    answer: str

    def as_pair(self) -> list[str]:
        return [self.question, self.answer]


def clean_history_text(text: Any) -> str:
    if text is None:
        return ""

    cleaned = str(text)
    for marker in ("\n\n---\n\n🖼️ Related Images", "🖼️ Related Images"):
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0]

    cleaned = cleaned.replace("🧠 Answer", "")
    cleaned = _DATA_IMAGE_RE.sub("[image omitted]", cleaned)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = unescape(cleaned)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def normalize_chat_history(
    chat_history: Iterable[Any] | None,
    max_turns: int = 10,
    max_chars: int = 10000,
) -> list[ChatTurn]:
    if not chat_history:
        return []

    turns: list[ChatTurn] = []
    pending_user = ""

    for item in chat_history:
        if isinstance(item, dict):
            role = item.get("role")
            content = clean_history_text(item.get("content"))
            if not content:
                continue
            if role == "user":
                pending_user = content
            elif role == "assistant" and pending_user:
                turns.append(ChatTurn(pending_user, content))
                pending_user = ""
            continue

        if isinstance(item, (list, tuple)) and len(item) == 2:
            question = clean_history_text(item[0])
            answer = clean_history_text(item[1])
            if question and answer:
                turns.append(ChatTurn(question, answer))

    return limit_chat_history(turns, max_turns=max_turns, max_chars=max_chars)


def limit_chat_history(
    turns: Iterable[ChatTurn],
    max_turns: int = 10,
    max_chars: int = 10000,
) -> list[ChatTurn]:
    if max_turns <= 0 or max_chars <= 0:
        return []

    limited: list[ChatTurn] = []
    total_chars = 0
    recent_turns = list(turns)[-max_turns:]

    for turn in reversed(recent_turns):
        turn_chars = len(turn.question) + len(turn.answer)
        if limited and total_chars + turn_chars > max_chars:
            break
        if turn_chars > max_chars:
            answer_budget = max(0, max_chars - len(turn.question))
            turn = ChatTurn(turn.question, turn.answer[:answer_budget].rstrip())
            turn_chars = len(turn.question) + len(turn.answer)
        limited.insert(0, turn)
        total_chars += turn_chars

    return limited


def build_contextual_retrieval_query(question: str, chat_history: Iterable[Any] | None, max_turns: int = 3) -> str:
    clean_question = clean_history_text(question)
    turns = normalize_chat_history(chat_history, max_turns=max_turns, max_chars=2500)
    if not turns:
        return clean_question

    prior = "\n".join(
        f"Previous user question: {turn.question}\nPrevious assistant answer: {turn.answer[:500]}"
        for turn in turns
    )
    return f"{prior}\nCurrent user question: {clean_question}"


def build_chat_messages(
    system_prompt: str,
    prompt: str,
    chat_history: Iterable[Any] | None,
    max_turns: int = 10,
    max_chars: int = 10000,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}]
    for turn in normalize_chat_history(chat_history, max_turns=max_turns, max_chars=max_chars):
        messages.append({"role": "user", "content": turn.question})
        messages.append({"role": "assistant", "content": turn.answer})
    messages.append({"role": "user", "content": prompt})
    return messages


def append_chat_turn(
    chat_history: Iterable[Any] | None,
    question: str,
    answer: str,
    max_turns: int = 10,
    max_chars: int = 10000,
) -> list[list[str]]:
    turns = normalize_chat_history(chat_history, max_turns=max_turns, max_chars=max_chars)
    turns.append(ChatTurn(clean_history_text(question), clean_history_text(answer)))
    return [turn.as_pair() for turn in limit_chat_history(turns, max_turns=max_turns, max_chars=max_chars)]
