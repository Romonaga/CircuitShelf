"""LLM-backed answer validation and cleanup for RAG responses."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable


RESPONSE_FINALIZER_SYSTEM_PROMPT = (
    "You are CircuitShelf's response finalizer. Review retrieval-grounded electronics "
    "answers for usefulness, source grounding, wiring safety, and readability. Preserve "
    "correct technical content. Do not add unsupported pinouts, component values, or "
    "claims. Return JSON only."
)

WIRING_INTENT_PATTERN = re.compile(
    r"\b(wire|wiring|connect|hook\s*up|breadboard|pinout|pin-by-pin|assembly|build card)\b",
    re.IGNORECASE,
)
SOURCE_REFERENCE_PATTERN = re.compile(r"\b(source|page|datasheet|book|context|retrieved)\b", re.IGNORECASE)


@dataclass
class ResponseValidationResult:
    enabled: bool = False
    ran: bool = False
    useful: bool = True
    changed: bool = False
    confidence: float | None = None
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    elapsed_ms: int = 0
    model: str | None = None

    def api_payload(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "ran": self.ran,
            "useful": self.useful,
            "changed": self.changed,
            "confidence": self.confidence,
            "issues": self.issues,
            "notes": self.notes,
            "elapsedMs": self.elapsed_ms,
            "model": self.model,
        }


def deterministic_response_issues(
    question: str,
    answer: str,
    source_payload: list[dict],
    build_card: dict | None,
) -> list[str]:
    issues = []
    question_text = question or ""
    answer_text = answer or ""

    if not answer_text.strip():
        issues.append("The model returned an empty answer.")
    if answer_text.strip() == "[LLM error]" or "[LLM error]" in answer_text:
        issues.append("The model returned an LLM error marker.")
    if source_payload and not SOURCE_REFERENCE_PATTERN.search(answer_text):
        issues.append("The answer does not clearly reference the retrieved material.")
    if WIRING_INTENT_PATTERN.search(question_text):
        lowered = answer_text.lower()
        if "gnd" not in lowered and "ground" not in lowered:
            issues.append("The wiring answer does not mention ground/common-ground checks.")
        if "power" not in lowered and "vcc" not in lowered and "supply" not in lowered and "voltage" not in lowered:
            issues.append("The wiring answer does not clearly state power or voltage requirements.")
    if build_card:
        if not build_card.get("parts"):
            issues.append("The build card has no parts list.")
        if not build_card.get("wiring"):
            issues.append("The build card has no wiring steps.")
        if not build_card.get("checks"):
            issues.append("The build card has no pre-power checks.")
        if not build_card.get("warnings"):
            issues.append("The build card has no warnings.")
    return _dedupe_strings(issues)


def should_run_response_finalizer(
    *,
    enabled: bool,
    mode: str,
    confidence: Any,
    build_card: dict | None,
    issues: list[str],
    min_confidence: float,
) -> bool:
    if not enabled:
        return False
    normalized_mode = (mode or "always").strip().lower()
    if normalized_mode == "off":
        return False
    if normalized_mode == "always":
        return True
    if normalized_mode in {"issues", "issues_only"}:
        return bool(issues)
    if normalized_mode in {"build", "build_cards"}:
        return bool(build_card)
    if normalized_mode in {"build_or_issues", "issues_or_build"}:
        return bool(build_card or issues)
    if normalized_mode in {"low_confidence", "low-confidence"}:
        return _optional_float(confidence, 1.0) < min_confidence
    if normalized_mode in {"build_or_low_confidence", "low_confidence_or_build"}:
        return bool(build_card) or _optional_float(confidence, 1.0) < min_confidence
    return True


def build_response_finalizer_prompt(
    *,
    question: str,
    answer: str,
    source_payload: list[dict],
    build_card: dict | None,
    deterministic_issues: list[str],
    max_context_chars: int = 7000,
) -> str:
    payload = {
        "question": question,
        "answer": answer,
        "deterministicIssues": deterministic_issues,
        "sources": _source_summaries(source_payload, max_context_chars=max_context_chars),
        "buildCard": build_card,
    }
    schema = {
        "useful": True,
        "confidence": 0.0,
        "issues": ["short issue text"],
        "notes": ["short validation note"],
        "revisedAnswer": "Markdown answer to show the user",
    }
    return (
        "Validate and clean up this CircuitShelf answer.\n"
        f"Return ONLY this JSON shape with these exact top-level keys: {json.dumps(schema, ensure_ascii=False)}\n"
        "Do not echo the input object. Do not include question, answer, sources, buildCard, or deterministicIssues as top-level keys.\n"
        "Rules:\n"
        "- Keep only facts supported by the answer and retrieved source summaries.\n"
        "- Improve Markdown structure and readability.\n"
        "- For wiring/build answers, make power, ground, pin-by-pin steps, checks, and warnings explicit when supported.\n"
        "- If something important is missing, say what must be verified instead of guessing.\n"
        "- Remove unrelated build-card content.\n"
        "- Return JSON only. Do not wrap it in Markdown.\n\n"
        f"Input to review:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def parse_response_finalizer_output(
    raw: str,
    *,
    fallback_answer: str,
    deterministic_issues: list[str],
) -> tuple[str, ResponseValidationResult]:
    data = _extract_json_value(raw)
    if not isinstance(data, dict):
        return fallback_answer, ResponseValidationResult(
            enabled=True,
            ran=True,
            useful=True,
            changed=False,
            issues=deterministic_issues + ["Response finalizer did not return valid JSON."],
        )

    schema_issue = []
    if "revisedAnswer" not in data:
        schema_issue.append("Response finalizer did not return the requested review schema.")
    revised = _clean_answer(data.get("revisedAnswer"), 20_000) or fallback_answer
    issues = _normalize_strings(data.get("issues"), 12)
    notes = _normalize_strings(data.get("notes"), 8)
    result = ResponseValidationResult(
        enabled=True,
        ran=True,
        useful=bool(data.get("useful", not schema_issue)),
        changed=_normalize_answer(revised) != _normalize_answer(fallback_answer),
        confidence=_bounded_float(data.get("confidence")),
        issues=_dedupe_strings(deterministic_issues + schema_issue + issues)[:16],
        notes=notes,
    )
    return revised, result


def finalize_response(
    *,
    question: str,
    answer: str,
    source_payload: list[dict],
    build_card: dict | None,
    model_name: str,
    confidence: Any,
    enabled: bool,
    mode: str,
    min_confidence: float,
    max_context_chars: int,
    llm_call: Callable[[str], str],
) -> tuple[str, ResponseValidationResult]:
    issues = deterministic_response_issues(question, answer, source_payload, build_card)
    if not should_run_response_finalizer(
        enabled=enabled,
        mode=mode,
        confidence=confidence,
        build_card=build_card,
        issues=issues,
        min_confidence=min_confidence,
    ):
        return answer, ResponseValidationResult(enabled=enabled, ran=False, useful=not issues, issues=issues)

    prompt = build_response_finalizer_prompt(
        question=question,
        answer=answer,
        source_payload=source_payload,
        build_card=build_card,
        deterministic_issues=issues,
        max_context_chars=max_context_chars,
    )
    started_at = time.time()
    raw = llm_call(prompt)
    revised, result = parse_response_finalizer_output(raw, fallback_answer=answer, deterministic_issues=issues)
    result.elapsed_ms = int((time.time() - started_at) * 1000)
    result.model = model_name
    return revised, result


def _source_summaries(source_payload: list[dict], *, max_context_chars: int) -> list[dict]:
    rows = []
    remaining = max(500, int(max_context_chars or 7000))
    for source in (source_payload or [])[:10]:
        chunks = []
        for chunk in source.get("chunks") or []:
            preview = _clean_text(chunk.get("preview") or chunk.get("text"), min(600, remaining))
            if not preview:
                continue
            remaining -= len(preview)
            chunks.append(
                {
                    "page": chunk.get("page"),
                    "section": chunk.get("section"),
                    "category": chunk.get("category"),
                    "preview": preview,
                }
            )
            if remaining <= 0 or len(chunks) >= 5:
                break
        rows.append(
            {
                "source": source.get("source"),
                "displayName": source.get("displayName"),
                "pages": source.get("pages") or [],
                "chunkCount": source.get("chunkCount") or 0,
                "chunks": chunks,
            }
        )
        if remaining <= 0:
            break
    return rows


def _extract_json_value(raw: str):
    text = str(raw or "").strip()
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    candidates = [text]
    left = text.find("{")
    right = text.rfind("}")
    if left >= 0 and right > left:
        candidates.append(text[left:right + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _normalize_strings(value, limit: int) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return _dedupe_strings([_clean_text(item, 280) for item in value or [] if _clean_text(item, 280)])[:limit]


def _clean_text(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _clean_answer(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _normalize_answer(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _bounded_float(value) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _optional_float(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _dedupe_strings(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
