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

BENCH_PHOTO_VERIFICATION_INSTRUCTIONS = (
    "You are CircuitShelf's bench photo inspection assistant. Return JSON only. "
    "Compare the uploaded electronics bench photo to the specific build step and diagnostics. "
    "Be conservative: do not claim the full circuit is correct, electrically safe, or ready to power. "
    "Use status looks_consistent only when the visible photo evidence appears consistent with the step. "
    "Use needs_attention when visible issues or quality problems should be addressed. "
    "Use cannot_verify when the photo does not show enough evidence."
)

PROJECT_FINDER_TRIAGE_INSTRUCTIONS = (
    "You are CircuitShelf's Project Finder triage assistant. Return compact JSON only. "
    "Do not invent components or claim a project is buildable without evidence."
)

LOCAL_CIRCUIT_GRAPH_ENRICHMENT_SYSTEM_PROMPT = (
    "You are CircuitShelf's local circuit graph reviewer. Return compact JSON only. "
    "Use only the assembly plan, existing graph, and cited evidence. Be conservative: "
    "do not invent pins, nets, values, packages, or PCB-ready topology."
)

CIRCUIT_GRAPH_ENRICHMENT_INSTRUCTIONS = (
    "You are CircuitShelf's circuit graph enrichment assistant. Return compact JSON only. "
    "Use only the provided assembly plan and graph. Do not invent unsupported electronics facts."
)

LOCAL_CONVERSATION_BENCH_PLAN_SYSTEM_PROMPT = (
    "You are CircuitShelf's local Ask-to-Bench plan synthesizer. Return strict JSON only. "
    "Use only the conversation transcript and retrieved source summaries. Be conservative: "
    "do not invent pins, voltages, component values, or safety-critical steps."
)

CONVERSATION_BENCH_PLAN_INSTRUCTIONS = (
    "You are CircuitShelf's Ask-to-Bench plan synthesizer. Return strict JSON only. "
    "Use only the conversation transcript and retrieved source summaries. Do not invent unsupported electronics facts."
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


def build_bench_photo_verification_prompt(
    *,
    plan: dict[str, Any],
    step: dict[str, Any],
    note: str,
    diagnostics: dict[str, Any],
    local_review: dict[str, Any] | None = None,
) -> str:
    return (
        "Inspect this bench photo for one CircuitShelf build step. Return compact JSON with keys: "
        "status, confidence, summary, findings, requestedEvidence. "
        "status must be one of looks_consistent, needs_attention, cannot_verify. "
        "confidence must be 0.0-1.0. findings and requestedEvidence must be arrays of short strings. "
        "Do not infer hidden connections. Do not say the circuit is safe or fully correct.\n\n"
        f"Plan: {plan.get('title') or 'Assembly plan'}\n"
        f"Objective: {plan.get('objective') or ''}\n"
        f"Step: {step.get('ordinal')}. {step.get('title')} -> {step.get('instruction')} {step.get('note') or ''}\n"
        f"User note: {note[:1000]}\n"
        f"Image diagnostics: {json.dumps(diagnostics, sort_keys=True)[:3000]}\n"
        f"Local review: {json.dumps(local_review or {}, sort_keys=True)[:2000]}"
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


def build_circuit_graph_enrichment_prompt(
    *,
    plan: dict[str, Any],
    graph: dict[str, Any],
    local_review: dict[str, Any] | None = None,
) -> str:
    compact_plan = {
        "id": plan.get("id"),
        "title": plan.get("title"),
        "objective": plan.get("objective"),
        "componentName": plan.get("componentName"),
        "componentType": plan.get("componentType"),
        "summary": str(plan.get("summary") or "")[:1200],
        "parts": (plan.get("parts") or [])[:40],
        "power": (plan.get("power") or [])[:12],
        "steps": [
            {
                "id": step.get("id"),
                "ordinal": step.get("ordinal"),
                "type": step.get("type"),
                "title": step.get("title"),
                "instruction": step.get("instruction"),
                "note": step.get("note"),
                "sourcePath": step.get("sourcePath"),
                "page": step.get("page"),
            }
            for step in (plan.get("steps") or [])[:80]
        ],
        "sources": (plan.get("sources") or [])[:20],
    }
    compact_graph = {
        "status": graph.get("status"),
        "components": (graph.get("components") or [])[:60],
        "pins": (graph.get("pins") or [])[:100],
        "nets": (graph.get("nets") or [])[:80],
        "connections": (graph.get("connections") or [])[:100],
        "validationFindings": (graph.get("validationFindings") or [])[:80],
        "stats": graph.get("stats") or {},
    }
    return (
        "Review and enrich this CircuitShelf circuit graph. Return JSON with keys: "
        "useful, confidence, summary, proposedPins, proposedNets, proposedConnections, "
        "validationFindings, escalateToOpenAI, reason. useful and escalateToOpenAI are booleans. "
        "confidence is 0.0-1.0. proposedPins/proposedNets/proposedConnections/validationFindings are arrays. "
        "Every proposed item must include evidenceStepId or sourcePath/page when evidence exists. "
        "Do not mark the graph PCB-ready if concrete pin numbers or circuit nets are missing. "
        "Prefer adding validation findings over guessing.\n\n"
        f"Assembly plan: {json.dumps(compact_plan, sort_keys=True)[:12000]}\n\n"
        f"Current graph: {json.dumps(compact_graph, sort_keys=True)[:12000]}\n\n"
        f"Local review: {json.dumps(local_review or {}, sort_keys=True)[:5000]}"
    )


def build_conversation_bench_plan_prompt(
    *,
    objective: str,
    conversation: dict[str, Any],
    source_payload: list[dict[str, Any]],
    local_review: dict[str, Any] | None = None,
) -> str:
    turns = []
    for turn in (conversation.get("turns") or [])[-10:]:
        turns.append(
            {
                "ordinal": turn.get("ordinal"),
                "question": str(turn.get("question") or "")[:1800],
                "answer": str(turn.get("answer") or "")[:2400],
                "confidence": turn.get("confidence"),
            }
        )
    sources = []
    for source in (source_payload or [])[:12]:
        chunks = []
        for chunk in source.get("chunks") or []:
            chunks.append(
                {
                    "page": chunk.get("page"),
                    "section": chunk.get("section"),
                    "preview": str(chunk.get("preview") or "")[:420],
                }
            )
        sources.append(
            {
                "source": source.get("source"),
                "displayName": source.get("displayName"),
                "pages": source.get("pages") or [],
                "chunkCount": source.get("chunkCount") or source.get("chunks") or 0,
                "chunks": chunks[:4],
            }
        )
    payload = {
        "objective": objective,
        "conversationTitle": conversation.get("title"),
        "turns": turns,
        "sources": sources,
        "localReview": local_review or {},
        "schema": {
            "title": "short bench project title",
            "componentName": "main component or project family",
            "componentType": "component category",
            "summary": "one paragraph",
            "confidence": 0.0,
            "parts": [{"name": "part", "detail": "why/value/package"}],
            "power": ["power note"],
            "wiring": [{"from": "pin/component/rail", "to": "pin/component/rail", "note": "specific instruction", "page": None}],
            "checks": ["verification step"],
            "warnings": ["safety, evidence, or uncertainty warning"],
            "sourceNotes": [{"source": "source path/name", "pages": [1], "chunks": 1}],
            "useful": True,
            "escalateToOpenAI": False,
            "reason": "short reason",
        },
    }
    return (
        "Create one CircuitShelf Bench assembly plan JSON object from this Ask conversation. "
        "Only produce a plan when the conversation contains a concrete low-voltage electronics project or wiring objective. "
        "Prefer pin-by-pin wiring only when the conversation or source evidence supports it. "
        "If required pins, component values, or safety-critical information are missing, include warnings and checks. "
        "If a useful plan cannot be formed, return JSON with useful=false, escalateToOpenAI as appropriate, and reason. "
        "Do not use a fixed recipe for any specific chip unless the conversation calls for it.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
