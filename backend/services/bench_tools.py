from __future__ import annotations

import base64
import io
import json
import math
import re
from collections import Counter
from typing import Any

import numpy as np
from PIL import Image, ImageFilter, ImageStat


def analyze_bench_photo(image_bytes: bytes) -> dict[str, Any]:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = image.size
    small = image.resize((min(width, 640), max(1, round(height * min(width, 640) / max(width, 1)))))
    gray = small.convert("L")
    stat = ImageStat.Stat(gray)
    brightness = float(stat.mean[0])
    contrast = float(stat.stddev[0])
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_array = np.asarray(edges, dtype=np.float32)
    gray_array = np.asarray(gray, dtype=np.float32)
    edge_density = float(np.mean(edge_array > 38.0))
    blur_score = laplacian_variance(gray_array)
    color_summary = dominant_color_summary(small)
    wire_color_counts = wire_like_color_counts(small)
    warnings = photo_diagnostic_warnings(width, height, brightness, contrast, edge_density, blur_score)
    return {
        "width": width,
        "height": height,
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "edgeDensity": round(edge_density, 4),
        "blurScore": round(blur_score, 2),
        "dominantColors": color_summary,
        "wireColorPixels": wire_color_counts,
        "warnings": warnings,
    }


def laplacian_variance(gray_array: np.ndarray) -> float:
    center = gray_array[1:-1, 1:-1] * -4.0
    laplacian = (
        center
        + gray_array[:-2, 1:-1]
        + gray_array[2:, 1:-1]
        + gray_array[1:-1, :-2]
        + gray_array[1:-1, 2:]
    )
    return float(np.var(laplacian))


def dominant_color_summary(image: Image.Image) -> list[dict[str, Any]]:
    quantized = image.resize((160, 160)).quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    counts = quantized.getcolors(maxcolors=4096) or []
    total = sum(count for count, _ in counts) or 1
    result = []
    for count, index in sorted(counts, reverse=True)[:6]:
        offset = index * 3
        rgb = tuple(palette[offset : offset + 3])
        result.append({
            "hex": "#{:02x}{:02x}{:02x}".format(*rgb),
            "percent": round((count / total) * 100, 1),
        })
    return result


def wire_like_color_counts(image: Image.Image) -> dict[str, int]:
    array = np.asarray(image.resize((320, max(1, round(image.height * 320 / max(image.width, 1))))), dtype=np.int16)
    r = array[:, :, 0]
    g = array[:, :, 1]
    b = array[:, :, 2]
    masks = {
        "red": (r > 140) & (r > g * 1.35) & (r > b * 1.35),
        "green": (g > 120) & (g > r * 1.25) & (g > b * 1.25),
        "blue": (b > 120) & (b > r * 1.25) & (b > g * 1.2),
        "yellow": (r > 140) & (g > 120) & (b < 100),
        "black": (r < 65) & (g < 65) & (b < 65),
        "white": (r > 210) & (g > 210) & (b > 210),
    }
    return {name: int(np.sum(mask)) for name, mask in masks.items()}


def photo_diagnostic_warnings(width: int, height: int, brightness: float, contrast: float, edge_density: float, blur_score: float) -> list[str]:
    warnings = []
    if min(width, height) < 720:
        warnings.append("Photo resolution is low; close-up wire checks may be unreliable.")
    if brightness < 70:
        warnings.append("Image appears dark. Add bench lighting before relying on visual inspection.")
    if brightness > 220:
        warnings.append("Image appears overexposed. Reduce glare on IC markings and jumpers.")
    if contrast < 28:
        warnings.append("Low contrast may hide jumper positions or component labels.")
    if blur_score < 85:
        warnings.append("Image may be blurry. Retake with the camera steadier and focused on the breadboard.")
    if edge_density < 0.025:
        warnings.append("Few edges detected; the circuit may be too far away or out of focus.")
    if edge_density > 0.34:
        warnings.append("Very dense edges detected; clutter may make manual tracing difficult.")
    return warnings


def build_photo_checklist(plan: dict, note: str = "", diagnostics: dict[str, Any] | None = None) -> str:
    open_steps = [step for step in plan.get("steps", []) if not step.get("completed")]
    relevant_steps = open_steps[:6] if open_steps else (plan.get("steps") or [])[:6]
    lines = [
        "Photo saved and analyzed for this Bench plan.",
        "This is diagnostic assistance, not guaranteed wire tracing.",
        "",
    ]
    if diagnostics:
        lines.extend([
            "Image diagnostics:",
            f"- Resolution: {diagnostics.get('width')} x {diagnostics.get('height')}",
            f"- Brightness: {diagnostics.get('brightness')}",
            f"- Contrast: {diagnostics.get('contrast')}",
            f"- Edge density: {diagnostics.get('edgeDensity')}",
            f"- Blur score: {diagnostics.get('blurScore')}",
        ])
        wire_counts = diagnostics.get("wireColorPixels") or {}
        if wire_counts:
            visible = ", ".join(f"{key}: {value}" for key, value in wire_counts.items() if int(value or 0) > 0)
            lines.append(f"- Wire-like color pixels: {visible or 'none detected'}")
        for warning in diagnostics.get("warnings") or []:
            lines.append(f"- Warning: {warning}")
        lines.append("")
    lines.extend([
        "Manual checks to perform against the photo:",
        "- Power rails are clearly identified before power is applied.",
        "- Ground and VCC are not swapped.",
        "- IC notch/orientation matches the pin numbering used by the plan.",
        "- Every LED path has a current-limiting resistor.",
        "- Loose jumpers do not bridge adjacent rows accidentally.",
    ])
    if note:
        lines.extend(["", f"User note: {note}"])
    if relevant_steps:
        lines.append("")
        lines.append("Plan steps to compare against the photo:")
        for step in relevant_steps:
            lines.append(f"- Step {step['ordinal']}: {step['title']} -> {step['instruction']}")
    return "\n".join(lines)


LOCAL_STEP_PHOTO_REVIEW_SYSTEM_PROMPT = (
    "You are CircuitShelf's local bench photo inspection triage assistant. "
    "You cannot see the photo pixels directly; you only receive image diagnostics and the build step text. "
    "Return compact JSON only. Be conservative and never claim the circuit or wiring is correct. "
    "Allowed status values are needs_attention or cannot_verify."
)


def step_for_id(plan: dict, step_id: str | None) -> dict | None:
    if not step_id:
        return None
    return next((step for step in plan.get("steps") or [] if str(step.get("id")) == str(step_id)), None)


def build_step_photo_local_prompt(
    *,
    plan: dict,
    step: dict,
    note: str,
    diagnostics: dict[str, Any],
) -> str:
    return (
        "Review whether these photo diagnostics are adequate for assisted bench inspection of one build step. "
        "Return JSON with keys: status, confidence, summary, findings, requestedEvidence, escalateToOpenAI, reason. "
        "status must be needs_attention or cannot_verify. confidence must be 0.0-1.0. "
        "findings and requestedEvidence must be arrays of short strings. "
        "Set escalateToOpenAI true only when the image appears usable enough for vision inspection and the user is asking about a concrete step.\n\n"
        f"Plan: {plan.get('title') or 'Assembly plan'}\n"
        f"Step: {step.get('ordinal')}. {step.get('title')} -> {step.get('instruction')} {step.get('note') or ''}\n"
        f"User note: {note[:1000]}\n"
        f"Diagnostics: {json.dumps(diagnostics, sort_keys=True)[:3000]}"
    )


def build_step_photo_checklist(
    *,
    plan: dict,
    step: dict | None,
    note: str = "",
    diagnostics: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
) -> str:
    lines = [
        "Photo saved for Bench inspection.",
        "This is confidence-based assistance, not proof that the circuit is correct or electrically safe.",
        "",
    ]
    if step:
        lines.extend([
            f"Step inspected: {step.get('ordinal')}. {step.get('title')}",
            f"Instruction: {step.get('instruction')}",
        ])
        if step.get("note"):
            lines.append(f"Step note: {step.get('note')}")
        lines.append("")
    if verification:
        lines.extend([
            "Inspection result:",
            f"- Status: {verification.get('status') or 'cannot_verify'}",
            f"- Confidence: {verification.get('confidence') if verification.get('confidence') is not None else 'n/a'}",
        ])
        if verification.get("summary"):
            lines.append(f"- Summary: {verification.get('summary')}")
        for finding in verification.get("findings") or []:
            lines.append(f"- Finding: {finding}")
        for requested in verification.get("requestedEvidence") or []:
            lines.append(f"- Next evidence: {requested}")
        lines.append("")
    if diagnostics:
        lines.extend([
            "Image diagnostics:",
            f"- Resolution: {diagnostics.get('width')} x {diagnostics.get('height')}",
            f"- Brightness: {diagnostics.get('brightness')}",
            f"- Contrast: {diagnostics.get('contrast')}",
            f"- Edge density: {diagnostics.get('edgeDensity')}",
            f"- Blur score: {diagnostics.get('blurScore')}",
        ])
        for warning in diagnostics.get("warnings") or []:
            lines.append(f"- Warning: {warning}")
        lines.append("")
    lines.extend([
        "Manual checks still required:",
        "- Confirm power is disconnected before moving jumpers.",
        "- Check rails, IC orientation, and pin numbering against the plan.",
        "- Verify continuity and expected resistance/voltage with a meter when the step depends on it.",
    ])
    if note:
        lines.extend(["", f"User note: {note}"])
    return "\n".join(lines)


def deterministic_step_photo_verification(
    *,
    step: dict | None,
    diagnostics: dict[str, Any],
    note: str = "",
    local_review: dict[str, Any] | None = None,
    openai_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if openai_review:
        return normalize_photo_verification(openai_review, provider="openai")
    if local_review:
        return normalize_photo_verification(local_review, provider="ollama")

    warnings = [str(item) for item in diagnostics.get("warnings") or []]
    score = 0.35
    try:
        width = int(diagnostics.get("width") or 0)
        height = int(diagnostics.get("height") or 0)
        brightness = float(diagnostics.get("brightness") or 0)
        contrast = float(diagnostics.get("contrast") or 0)
        edge_density = float(diagnostics.get("edgeDensity") or 0)
        blur_score = float(diagnostics.get("blurScore") or 0)
    except (TypeError, ValueError):
        width = height = 0
        brightness = contrast = edge_density = blur_score = 0.0

    if min(width, height) >= 720:
        score += 0.12
    if 80 <= brightness <= 210:
        score += 0.10
    if contrast >= 35:
        score += 0.08
    if 0.035 <= edge_density <= 0.24:
        score += 0.07
    if blur_score >= 110:
        score += 0.10
    score = max(0.1, min(0.72, score - min(len(warnings), 5) * 0.05))

    requested = []
    if warnings:
        requested.extend(warnings[:3])
    else:
        requested.append("Add a close-up photo that shows both ends of each jumper involved in this step.")
    if step:
        requested.append("Confirm this step with continuity or voltage measurements when applicable.")

    status = "needs_attention" if warnings else "cannot_verify"
    findings = [
        "Diagnostics can judge image quality but cannot prove wire placement.",
        f"Image appears suitable for assisted inspection with confidence {score:.2f}." if not warnings else "Image quality issues may limit inspection.",
    ]
    if note:
        findings.append(f"User note considered: {note[:180]}")

    return {
        "status": status,
        "confidence": round(score, 2),
        "summary": "Photo quality reviewed; visual wiring correctness still requires manual inspection.",
        "findings": findings,
        "requestedEvidence": requested,
        "provider": "diagnostics",
        "model": None,
        "raw": {},
    }


def normalize_photo_verification(review: dict[str, Any], *, provider: str) -> dict[str, Any]:
    status = str(review.get("status") or "cannot_verify").strip().lower()
    if status not in {"looks_consistent", "needs_attention", "cannot_verify"}:
        status = "cannot_verify"
    if provider != "openai" and status == "looks_consistent":
        status = "cannot_verify"
    try:
        confidence = float(review.get("confidence"))
    except (TypeError, ValueError):
        confidence = None
    if confidence is not None:
        confidence = round(max(0.0, min(1.0, confidence)), 2)
    findings = review.get("findings") or review.get("notes") or []
    requested = review.get("requestedEvidence") or review.get("requested_evidence") or []
    if isinstance(findings, str):
        findings = [findings]
    if isinstance(requested, str):
        requested = [requested]
    return {
        "status": status,
        "confidence": confidence,
        "summary": str(review.get("summary") or review.get("reason") or "")[:1000],
        "findings": [str(item)[:500] for item in findings[:8]],
        "requestedEvidence": [str(item)[:500] for item in requested[:6]],
        "provider": str(review.get("provider") or provider),
        "model": review.get("model"),
        "raw": review,
    }


def build_assembly_export(plan: dict, export_format: str) -> dict:
    requested = (export_format or "markdown").lower()
    if requested in {"md", "markdown"}:
        content = assembly_export_markdown(plan)
        return {"filename": f"{safe_export_name(plan)}.md", "mimeType": "text/markdown", "content": content}
    if requested in {"ltspice", "spice", "netlist"}:
        content = assembly_export_spice(plan)
        return {"filename": f"{safe_export_name(plan)}.cir", "mimeType": "text/plain", "content": content}
    if requested in {"falstad", "circuitjs"}:
        content = assembly_export_falstad(plan)
        return {"filename": f"{safe_export_name(plan)}-falstad.txt", "mimeType": "text/plain", "content": content}
    return {"filename": f"{safe_export_name(plan)}.txt", "mimeType": "text/plain", "content": assembly_export_markdown(plan)}


def safe_export_name(plan: dict) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]+", "-", plan.get("title") or "assembly-plan").strip("-")
    return name[:80] or "assembly-plan"


def assembly_export_markdown(plan: dict) -> str:
    lines = [
        f"# {plan.get('title')}",
        "",
        f"Objective: {plan.get('objective')}",
        f"Component: {plan.get('componentName')} ({plan.get('componentType')})",
        "",
        "## Parts",
    ]
    lines.extend(f"- {part['name']}: {part.get('detail') or ''}" for part in plan.get("parts", []))
    lines.extend(["", "## Power"])
    lines.extend(f"- {item['note']}" for item in plan.get("power", []))
    lines.extend(["", "## Steps"])
    for step in plan.get("steps", []):
        source = f" Source: {step.get('sourcePath')} page {step.get('page')}." if step.get("sourcePath") or step.get("page") else ""
        lines.append(f"{step['ordinal']}. [{step['type']}] {step['title']}: {step['instruction']} {step.get('note') or ''}{source}")
    lines.extend(["", "## Sources"])
    for source in plan.get("sources", []):
        pages = ", ".join(str(page) for page in source.get("pages") or [])
        lines.append(f"- {source['displayName']} pages {pages or 'n/a'}")
    return "\n".join(lines).strip() + "\n"


def assembly_export_spice(plan: dict) -> str:
    if is_555_plan(plan):
        return spice_555_astable(plan)
    if is_led_plan(plan):
        return spice_led_resistor(plan)
    return spice_notes_only(plan)


def is_555_plan(plan: dict) -> bool:
    text = plan_text(plan)
    return "555" in text or "lm555" in text or "ne555" in text or "timer" in str(plan.get("componentType", "")).lower()


def is_led_plan(plan: dict) -> bool:
    return "led" in plan_text(plan)


def plan_text(plan: dict) -> str:
    bits = [str(plan.get(key) or "") for key in ("title", "objective", "componentName", "componentType", "summary")]
    bits.extend(str(part.get("name") or "") for part in plan.get("parts", []))
    bits.extend(str(step.get("title") or "") + " " + str(step.get("instruction") or "") for step in plan.get("steps", []))
    return " ".join(bits).lower()


def spice_555_astable(plan: dict) -> str:
    values = extract_common_values(plan)
    r1 = values["resistors"][0] if values["resistors"] else "10k"
    r2 = values["resistors"][1] if len(values["resistors"]) > 1 else "100k"
    c1 = values["capacitors"][0] if values["capacitors"] else "10u"
    return "\n".join([
        f"* {plan.get('title')}",
        "* CircuitShelf recognized this as a 555-style timer plan.",
        "* Starter astable netlist. Verify pins, values, and NE555 model before simulation.",
        ".title CircuitShelf NE555 Astable Starter",
        "VCC VCC 0 DC 5",
        f"R1 VCC DIS {r1}",
        f"R2 DIS TIMING {r2}",
        f"C1 TIMING 0 {c1}",
        "CCTRL CTRL 0 10n",
        "RLED OUT LEDA 330",
        "DLED LEDA 0 DRED",
        "* Pin order below: GND TRIG OUT RESET CTRL THRESH DISCH VCC",
        "XU1 0 TIMING OUT VCC CTRL TIMING DIS VCC NE555",
        ".model DRED D(Is=1e-14 N=2 Vfwd=1.8)",
        "* Include or define an NE555 subcircuit named NE555 for your simulator.",
        "*.include NE555.sub",
        ".tran 0 5s 0 1ms",
        ".end",
        "",
    ])


def spice_led_resistor(plan: dict) -> str:
    values = extract_common_values(plan)
    resistor = values["resistors"][0] if values["resistors"] else "330"
    return "\n".join([
        f"* {plan.get('title')}",
        "* CircuitShelf recognized this as an LED/resistor starter circuit.",
        ".title CircuitShelf LED Starter",
        "V1 VCC 0 DC 5",
        f"R1 VCC LEDA {resistor}",
        "D1 LEDA 0 DLED",
        ".model DLED D(Is=1e-14 N=2 Vfwd=2.0)",
        ".op",
        ".end",
        "",
    ])


def spice_notes_only(plan: dict) -> str:
    lines = [
        f"* {plan.get('title')}",
        "* CircuitShelf could not infer a complete node-level SPICE circuit yet.",
        "* Use these Bench steps to create the schematic manually.",
        ".title CircuitShelf starter notes",
        "",
    ]
    for step in plan.get("steps", []):
        lines.append(f"* {step['ordinal']}. {step['title']} -> {step['instruction']} {step.get('note') or ''}")
    lines.extend([".end", ""])
    return "\n".join(lines)


def assembly_export_falstad(plan: dict) -> str:
    if is_led_plan(plan):
        return "\n".join([
            "$ 1 5.0E-6 10.20027730826997 50 5.0 50",
            "v 112 176 112 288 0 0 40.0 5.0 0.0 0.0 0.5",
            "r 112 176 240 176 0 330.0",
            "162 240 176 240 288 2 default-led 1 0 0 0.01",
            "w 240 288 112 288 0",
            "g 112 288 112 320 0",
            "",
            "# CircuitShelf LED starter. Adjust values to match the Bench plan.",
        ])
    return "\n".join([
        f"CircuitJS/Falstad starter notes for {plan.get('title')}",
        "",
        "CircuitShelf could not infer a full CircuitJS topology for this plan yet.",
        "Use these steps while drawing the schematic:",
        "",
        *[
            f"{step['ordinal']}. {step['title']} -> {step['instruction']} {step.get('note') or ''}"
            for step in plan.get("steps", [])
        ],
        "",
    ])


def extract_common_values(plan: dict) -> dict[str, list[str]]:
    text = plan_text(plan)
    resistors = normalize_values(re.findall(r"\b\d+(?:\.\d+)?\s*(?:k|m)?(?:ohm|Ω)?\b", text), default_suffix="")
    capacitors = normalize_values(re.findall(r"\b\d+(?:\.\d+)?\s*(?:p|n|u|µ|m)f\b", text), default_suffix="")
    resistor_values = [value for value in resistors if re.search(r"(ohm|Ω|k|m)$", value, re.IGNORECASE)]
    return {
        "resistors": resistor_values[:4],
        "capacitors": capacitors[:4],
    }


def normalize_values(values: list[str], default_suffix: str = "") -> list[str]:
    result = []
    for value in values:
        normalized = re.sub(r"\s+", "", value.lower().replace("Ω", "ohm").replace("µ", "u"))
        if normalized and normalized not in result:
            result.append(normalized + default_suffix)
    return result
