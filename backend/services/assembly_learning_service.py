from __future__ import annotations


def build_learning_payload(plan: dict, session: dict | None) -> dict:
    steps = plan.get("steps") or []
    current_ordinal = int((session or {}).get("currentOrdinal") or 1)
    current_step = next((step for step in steps if int(step.get("ordinal") or 0) == current_ordinal), None)
    if not current_step and steps:
        current_step = steps[0]
        current_ordinal = int(current_step.get("ordinal") or 1)
    prompt = learning_prompt_for_step(current_step) if current_step else ""
    return {
        "planId": plan.get("id"),
        "currentOrdinal": current_ordinal,
        "modeEnabled": bool((session or {}).get("modeEnabled", True)),
        "stepCount": len(steps),
        "currentStep": current_step,
        "prompt": prompt,
    }


def learning_prompt_for_step(step: dict) -> str:
    step_type = step.get("type")
    title = step.get("title") or "this step"
    if step_type == "wiring":
        return (
            f"Before doing step {step.get('ordinal')}, identify the source pin/rail and destination for {title}. "
            "Say what should be connected, then make the connection and verify continuity before moving on."
        )
    if step_type == "warning":
        return f"Pause on caution step {step.get('ordinal')}. Explain the risk in your own words before continuing."
    return f"Before checking step {step.get('ordinal')}, predict what a correct circuit should show, then perform the test."


def update_learning_session(assembly_plan_store, plan_id: str, user_id: int, plan: dict, payload) -> dict:
    session = assembly_plan_store.get_learning(plan_id, user_id) or assembly_plan_store.start_learning(plan_id, user_id)
    current = int((session or {}).get("currentOrdinal") or 1)
    action = str(payload.action or "").lower()
    if action == "next":
        current += 1
    elif action == "previous":
        current -= 1
    elif action == "disable":
        session = assembly_plan_store.update_learning(plan_id, user_id, current_ordinal=current, mode_enabled=False)
        return build_learning_payload(plan, session)
    elif payload.currentOrdinal is not None:
        current = int(payload.currentOrdinal)
    max_ordinal = max((int(step["ordinal"]) for step in plan.get("steps", [])), default=1)
    current = max(1, min(current, max_ordinal))
    session = assembly_plan_store.update_learning(plan_id, user_id, current_ordinal=current, mode_enabled=True)
    return build_learning_payload(plan, session)
