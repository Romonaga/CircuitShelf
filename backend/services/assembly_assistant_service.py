from __future__ import annotations

from fastapi.concurrency import run_in_threadpool


def build_assembly_assistant_prompt(plan: dict, message: str) -> str:
    steps = "\n".join(
        f"{step['ordinal']}. [{'done' if step['completed'] else 'open'}] {step['title']}: {step['instruction']} {step.get('note') or ''}"
        for step in plan.get("steps", [])
    )
    sources = "\n".join(
        f"- {source['displayName']} pages {', '.join(str(page) for page in source.get('pages') or [])}"
        for source in plan.get("sources", [])
    )
    notes = "\n".join(f"{note['role']}: {note['message']}" for note in (plan.get("notes") or [])[-8:])
    return (
        "You are CircuitShelf's electronics bench assistant. Use only the assembly plan, checklist, and source notes below. "
        "Give practical next-step guidance, checks to perform, expected readings or behavior when supported, and safety cautions. "
        "If the plan lacks enough evidence, say what is missing.\n\n"
        f"Assembly plan: {plan.get('title')}\n"
        f"Objective: {plan.get('objective')}\n"
        f"Component: {plan.get('componentName')} ({plan.get('componentType')})\n"
        f"Summary: {plan.get('summary')}\n\n"
        f"Checklist:\n{steps}\n\n"
        f"Sources:\n{sources}\n\n"
        f"Recent bench conversation:\n{notes}\n\n"
        f"User says: {message}\n\n"
        "Respond as a concise lab assistant."
    )


async def answer_assembly_assistant(
    *,
    assembly_plan_store,
    query_ollama_chat_with_retry,
    plan_id: str,
    user_id: int,
    plan: dict,
    message: str,
    model_name: str,
) -> dict:
    assembly_plan_store.add_note(plan_id, "user", message, user_id)
    prompt = build_assembly_assistant_prompt(plan, message)
    assistant_answer = await run_in_threadpool(query_ollama_chat_with_retry, prompt, model_name, [])
    assembly_plan_store.add_note(plan_id, "assistant", assistant_answer, user_id)
    return {"plan": assembly_plan_store.get(plan_id, user_id), "answer": assistant_answer}
