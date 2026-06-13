from __future__ import annotations

import json
from typing import Any

from backend.services.openai_assist_utils import compact_intelligence_for_prompt


ANSWER_VALIDATION_INSTRUCTIONS = (
    "You are CircuitShelf's OpenAI answer validator. Return only the requested JSON. "
    "Do not add unsupported electronics facts or component values."
)

FALLBACK_ANSWER_INSTRUCTIONS = (
    "You are CircuitShelf's electronics fallback assistant. Be concise, practical, "
    "and explicit about missing source grounding."
)

INGESTION_REVIEW_INSTRUCTIONS = (
    "You are CircuitShelf's ingestion QA assistant. Return only compact JSON. "
    "Focus on extraction quality, not circuit design advice."
)

LOCAL_INGESTION_REVIEW_SYSTEM_PROMPT = (
    "You are CircuitShelf's local ingestion QA reviewer for electronics documents. "
    "Return compact JSON only. Be conservative: do not invent pinouts, ratings, or "
    "component facts. Your job is to decide whether deterministic extraction is good "
    "enough or needs paid cloud repair."
)

DATASHEET_REPAIR_INSTRUCTIONS = (
    "You are CircuitShelf's deterministic datasheet intelligence repair assistant. "
    "Return only compact JSON. Prefer explicit pin-function tables and pin diagrams. "
    "Never invent unsupported component data."
)

INVENTORY_PHOTO_INSTRUCTIONS = (
    "You are CircuitShelf's inventory photo assistant. "
    "Return JSON only and keep uncertain observations marked with warnings."
)

PROJECT_FINDER_TRIAGE_INSTRUCTIONS = (
    "You are CircuitShelf's Project Finder triage assistant. Return compact JSON only. "
    "Do not invent components or claim a project is buildable without evidence."
)

LOCAL_PROJECT_FINDER_TRIAGE_SYSTEM_PROMPT = (
    "You are CircuitShelf's local Project Finder triage reviewer. Return compact JSON only. "
    "Review whether low-confidence electronics project candidates are useful and grounded. "
    "Be conservative: do not invent missing parts, circuit values, pinouts, or build steps."
)


def build_fallback_answer_prompt(question: str) -> str:
    return (
        "CircuitShelf could not find matching indexed documents for this electronics question.\n"
        "Answer from general electronics knowledge only if you can do so safely. Begin by saying "
        "that no indexed source matched. If the request needs a datasheet, exact pinout, mains wiring, "
        "or safety-critical values, say what must be verified instead of guessing.\n\n"
        f"Question: {question}"
    )


def build_ingestion_review_prompt(
    *,
    source_path: str,
    is_global: bool,
    stats: dict[str, Any],
    sample_text: str,
) -> str:
    return (
        "Review this CircuitShelf document ingestion result. Return compact JSON with keys: "
        "quality, useful, warnings, suggestedReviewFocus. Do not infer facts not present in the sample.\n\n"
        f"Source: {source_path}\n"
        f"Scope: {'global corpus' if is_global else 'entity private'}\n"
        f"Stats: {json.dumps(stats, sort_keys=True)}\n\n"
        f"Sample extracted text:\n{sample_text[:6000]}"
    )


def build_local_ingestion_review_prompt(
    *,
    source_path: str,
    stats: dict[str, Any],
    sample_text: str,
    deterministic_reasons: list[str],
) -> str:
    return (
        "Review this CircuitShelf ingestion result before any paid cloud call is used. "
        "Return compact JSON with keys: quality, useful, confidence, warnings, "
        "suggestedReviewFocus, escalateToOpenAI, reason. "
        "quality must be one of good, usable, weak, poor. "
        "useful and escalateToOpenAI must be booleans. "
        "confidence must be 0.0-1.0. "
        "Escalate only when the document appears to be an electronics component/device "
        "datasheet and the extracted text is missing important pinout/fact evidence, "
        "or when OCR/text extraction looks too weak to trust. "
        "Do not ask for OpenAI just to polish wording.\n\n"
        f"Source: {source_path}\n"
        f"Deterministic review reasons: {json.dumps(deterministic_reasons)}\n"
        f"Stats: {json.dumps(stats, sort_keys=True)}\n\n"
        f"Sample extracted text:\n{sample_text[:6000]}"
    )


def build_datasheet_repair_prompt(
    *,
    source_path: str,
    is_global: bool,
    local_intelligence: dict[str, Any],
    sample_text: str,
) -> str:
    return (
        "Repair this CircuitShelf datasheet intelligence record using only the provided extracted text. "
        "Return compact JSON only with keys: componentName, componentType, summary, confidence, facts, pinout, notes. "
        "facts must be a list of objects with type, label, value, unit, page, evidence. "
        "pinout must be an object with pins, where pins is a list of objects with pin, label, function, page, evidence. "
        "Do not guess missing pins, voltages, current limits, or packages. If evidence is absent, leave the field empty.\n\n"
        f"Source: {source_path}\n"
        f"Scope: {'global corpus' if is_global else 'entity private'}\n"
        f"Local intelligence: {json.dumps(compact_intelligence_for_prompt(local_intelligence), sort_keys=True)}\n\n"
        f"Extracted text excerpts:\n{sample_text[:9000]}"
    )


def build_inventory_photo_prompt(note: str) -> str:
    return (
        "Identify electronics inventory visible in this photo. Return only compact JSON with key items. "
        "items must be an array of objects with displayName, partType, quantity, aliases, notes, confidence, warnings. "
        "Use conservative quantities: if you cannot count items, use 1 and add a warning. "
        "Prefer useful inventory names such as 'Red LED', 'NE555 timer IC', '10 kOhm resistor assortment'. "
        "Do not invent exact part numbers unless markings are visible.\n\n"
        f"User note: {note[:1000]}"
    )


def build_project_finder_triage_prompt(
    *,
    candidates: list[dict[str, Any]],
    deterministic_reason: str,
) -> str:
    compact_candidates = []
    for candidate in candidates:
        compact_candidates.append(
            {
                "id": candidate.get("id"),
                "title": candidate.get("title"),
                "score": candidate.get("score"),
                "buildable": candidate.get("buildable"),
                "summary": str(candidate.get("summary") or "")[:1200],
                "matchedParts": [
                    part.get("displayName") or part.get("name")
                    for part in candidate.get("matchedParts") or []
                ][:12],
                "requiredParts": [
                    part.get("displayName") or part.get("name")
                    for part in candidate.get("requiredParts") or []
                ][:16],
                "missingParts": [
                    part.get("displayName") or part.get("name")
                    for part in candidate.get("missingParts") or []
                ][:16],
                "caveats": (candidate.get("rejectionReasons") or [])[:6],
            }
        )
    return (
        "Review these CircuitShelf Project Finder candidates after deterministic retrieval. "
        "Return JSON with key candidates, an array of objects with keys: id, useful, confidence, "
        "recommendedAction, notes, escalateToOpenAI, reason. "
        "useful and escalateToOpenAI must be booleans. confidence must be 0.0-1.0. "
        "recommendedAction must be one of keep, demote, needs_parts, manual_review. "
        "Escalate to OpenAI only when the candidate could be useful but the local evidence is too ambiguous "
        "to decide confidently. Do not escalate just to polish wording.\n\n"
        f"Deterministic reason: {deterministic_reason}\n"
        f"Candidates: {json.dumps(compact_candidates, sort_keys=True)}"
    )
