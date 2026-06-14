from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any


PIN_RE = re.compile(r"\bpin\s*([A-Za-z0-9._-]+)\b", re.IGNORECASE)
NUMERIC_PIN_RE = re.compile(r"\b([A-Za-z0-9._-]+)\s*[:/-]\s*([A-Za-z][A-Za-z0-9_+-]*)\b")
VALUE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:v|volt|volts|ma|amp|amps)\b", re.IGNORECASE)
GROUND_RE = re.compile(r"\b(gnd|ground|0v|negative rail|common ground)\b", re.IGNORECASE)
POWER_RE = re.compile(r"\b(vcc|vdd|vee|vin|v\+|positive rail|power rail|supply|battery|\d+(?:\.\d+)?\s*v)\b", re.IGNORECASE)
RAIL_RE = re.compile(r"\b(rail|bus|ground|gnd|vcc|vdd|supply|battery|0v)\b", re.IGNORECASE)


def build_circuit_graph(plan: dict[str, Any]) -> dict[str, Any]:
    """Build a conservative circuit graph from an existing Bench assembly plan."""
    builder = _CircuitGraphBuilder(plan)
    return builder.build()


class _CircuitGraphBuilder:
    def __init__(self, plan: dict[str, Any]):
        self.plan = plan or {}
        self.components: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.pins: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.nets: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.connections: list[dict[str, Any]] = []
        self.findings: list[dict[str, Any]] = []
        self._source_lookup = {
            str(source.get("sourcePath") or ""): source
            for source in self.plan.get("sources") or []
            if source.get("sourcePath")
        }

    def build(self) -> dict[str, Any]:
        for ordinal, part in enumerate(self.plan.get("parts") or [], start=1):
            self._component_for_part(part, ordinal)

        wiring_steps = [step for step in self.plan.get("steps") or [] if step.get("type") == "wiring"]
        for step in wiring_steps:
            self._add_wiring_step(step)

        for note in self.plan.get("power") or []:
            self._add_power_note(note)

        self._add_plan_findings(wiring_steps)
        status = "ready_for_export" if not any(item["severity"] == "blocking" for item in self.findings) else "needs_evidence"
        return {
            "schemaVersion": 1,
            "planId": self.plan.get("id"),
            "title": self.plan.get("title") or "Assembly plan",
            "status": status,
            "source": {
                "type": "assembly_plan",
                "status": self.plan.get("status"),
                "confidence": self.plan.get("confidence"),
            },
            "components": list(self.components.values()),
            "pins": list(self.pins.values()),
            "nets": list(self.nets.values()),
            "connections": self.connections,
            "validationFindings": self.findings,
            "stats": {
                "componentCount": len(self.components),
                "pinCount": len(self.pins),
                "netCount": len(self.nets),
                "connectionCount": len(self.connections),
                "blockingFindingCount": sum(1 for item in self.findings if item["severity"] == "blocking"),
                "warningFindingCount": sum(1 for item in self.findings if item["severity"] == "warning"),
            },
        }

    def _component_for_part(self, part: dict[str, Any], ordinal: int) -> dict[str, Any]:
        label = _clean(part.get("name")) or f"Part {ordinal}"
        component_id = f"component-{_slug(label) or ordinal}"
        existing = self.components.get(component_id)
        if existing:
            return existing
        component = {
            "id": component_id,
            "label": label,
            "name": label,
            "type": _infer_component_type(label, part.get("detail") or ""),
            "quantity": 1,
            "partId": part.get("id"),
            "detail": _clean(part.get("detail")),
            "evidence": [{"type": "assembly_part", "partId": part.get("id")}],
        }
        self.components[component_id] = component
        return component

    def _component_for_label(self, label: str, evidence: dict[str, Any]) -> dict[str, Any]:
        label = _clean(label) or _clean(self.plan.get("componentName")) or "Circuit node"
        component_id = f"component-{_slug(label)}"
        existing = self.components.get(component_id)
        if existing:
            _append_unique(existing["evidence"], evidence)
            return existing
        component = {
            "id": component_id,
            "label": label,
            "name": label,
            "type": _infer_component_type(label, ""),
            "quantity": 1,
            "partId": None,
            "detail": "",
            "evidence": [evidence],
        }
        self.components[component_id] = component
        return component

    def _pin_for_endpoint(self, endpoint: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any] | None:
        if endpoint["kind"] != "component":
            return None
        component = self._component_for_label(endpoint["componentLabel"], evidence)
        pin_label = endpoint.get("pinLabel") or endpoint.get("raw") or "unspecified"
        pin_number = endpoint.get("pinNumber")
        pin_id = f"{component['id']}-pin-{_slug(pin_number or pin_label)}"
        existing = self.pins.get(pin_id)
        if existing:
            _append_unique(existing["evidence"], evidence)
            return existing
        pin = {
            "id": pin_id,
            "componentId": component["id"],
            "componentLabel": component["label"],
            "pinNumber": pin_number,
            "label": pin_label,
            "function": endpoint.get("function") or _infer_pin_function(pin_label),
            "raw": endpoint.get("raw"),
            "evidence": [evidence],
        }
        self.pins[pin_id] = pin
        if not pin_number:
            self._finding(
                "blocking",
                "pin_number_missing",
                f"{component['label']} endpoint does not name a concrete pin number.",
                evidence,
            )
        return pin

    def _net_for_endpoint(self, endpoint: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        role = endpoint.get("role") or "signal"
        name = endpoint.get("netName") or endpoint.get("pinLabel") or endpoint.get("raw") or role
        if role == "ground":
            name = "GND"
        elif role == "power" and not VALUE_RE.search(name):
            name = _clean(name) or "Power"
        net_id = f"net-{_slug(role + '-' + name)}"
        existing = self.nets.get(net_id)
        if existing:
            _append_unique(existing["evidence"], evidence)
            return existing
        net = {
            "id": net_id,
            "name": name,
            "role": role,
            "evidence": [evidence],
            "connections": [],
        }
        self.nets[net_id] = net
        return net

    def _add_wiring_step(self, step: dict[str, Any]) -> None:
        evidence = self._step_evidence(step)
        left = _parse_endpoint(step.get("title") or "", self.plan)
        right = _parse_endpoint(step.get("instruction") or "", self.plan)

        if left["kind"] == "unknown" or right["kind"] == "unknown":
            self._finding("blocking", "connection_endpoint_unclear", "A wiring step has an unclear endpoint.", evidence)
            return

        net = self._connection_net(left, right, evidence)
        from_ref = self._endpoint_ref(left, net, evidence)
        to_ref = self._endpoint_ref(right, net, evidence)
        connection = {
            "id": f"connection-{len(self.connections) + 1}",
            "from": from_ref,
            "to": to_ref,
            "netId": net["id"],
            "instruction": step.get("note") or "",
            "evidence": evidence,
            "confidence": _connection_confidence(left, right),
        }
        self.connections.append(connection)
        net["connections"].append({"connectionId": connection["id"], "endpoint": from_ref})
        net["connections"].append({"connectionId": connection["id"], "endpoint": to_ref})
        if connection["confidence"] < 0.7:
            self._finding(
                "warning",
                "connection_needs_pin_review",
                "A connection was captured but needs pin-level review before PCB export.",
                evidence,
            )

    def _connection_net(self, left: dict[str, Any], right: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        if left["kind"] == "net":
            return self._net_for_endpoint(left, evidence)
        if right["kind"] == "net":
            return self._net_for_endpoint(right, evidence)
        labels = [left.get("pinLabel") or left.get("raw"), right.get("pinLabel") or right.get("raw")]
        name = " to ".join(_clean(label) for label in labels if label)
        return self._net_for_endpoint({"kind": "net", "role": "signal", "netName": name or "Signal"}, evidence)

    def _endpoint_ref(self, endpoint: dict[str, Any], net: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        if endpoint["kind"] == "net":
            return {"kind": "net", "netId": net["id"], "label": endpoint.get("raw") or net["name"]}
        pin = self._pin_for_endpoint(endpoint, evidence)
        return {
            "kind": "pin",
            "componentId": pin["componentId"] if pin else None,
            "pinId": pin["id"] if pin else None,
            "label": endpoint.get("raw"),
        }

    def _add_power_note(self, note: dict[str, Any]) -> None:
        text = note.get("note") if isinstance(note, dict) else str(note)
        if not _clean(text):
            return
        evidence = {"type": "power_note", "powerId": note.get("id") if isinstance(note, dict) else None, "text": _clean(text)}
        if GROUND_RE.search(text):
            self._net_for_endpoint({"kind": "net", "role": "ground", "raw": "GND", "netName": "GND"}, evidence)
        if POWER_RE.search(text):
            name_match = VALUE_RE.search(text)
            self._net_for_endpoint(
                {"kind": "net", "role": "power", "raw": text, "netName": name_match.group(0).upper() if name_match else "Power"},
                evidence,
            )

    def _add_plan_findings(self, wiring_steps: list[dict[str, Any]]) -> None:
        if not wiring_steps:
            self._finding(
                "blocking",
                "no_wiring_steps",
                "The assembly plan has no wiring steps to convert into a circuit graph.",
                {"type": "assembly_plan", "planId": self.plan.get("id")},
            )
        if not self.pins:
            self._finding(
                "blocking",
                "no_pin_evidence",
                "No pin-level evidence was found in the assembly plan.",
                {"type": "assembly_plan", "planId": self.plan.get("id")},
            )
        if not self.nets:
            self._finding(
                "blocking",
                "no_net_evidence",
                "No circuit nets could be derived from the assembly plan.",
                {"type": "assembly_plan", "planId": self.plan.get("id")},
            )

    def _step_evidence(self, step: dict[str, Any]) -> dict[str, Any]:
        source_path = step.get("sourcePath")
        source = self._source_lookup.get(str(source_path or ""), {})
        return {
            "type": "assembly_step",
            "stepId": step.get("id"),
            "ordinal": step.get("ordinal"),
            "sourcePath": source_path,
            "displayName": source.get("displayName"),
            "page": step.get("page"),
        }

    def _finding(self, severity: str, code: str, message: str, evidence: dict[str, Any]) -> None:
        item = {"severity": severity, "code": code, "message": message, "evidence": evidence}
        if item not in self.findings:
            self.findings.append(item)


def _parse_endpoint(text: str, plan: dict[str, Any]) -> dict[str, Any]:
    raw = _clean(text)
    if not raw:
        return {"kind": "unknown", "raw": raw}
    role = _infer_net_role(raw)
    pin_match = PIN_RE.search(raw)
    if pin_match:
        prefix = raw[: pin_match.start()].strip(" :-")
        suffix = raw[pin_match.end() :].strip(" :-")
        component = prefix or _clean(plan.get("componentName")) or "Component"
        return {
            "kind": "component",
            "raw": raw,
            "componentLabel": component,
            "pinNumber": pin_match.group(1),
            "pinLabel": suffix or pin_match.group(1),
            "role": role,
            "function": _infer_pin_function(suffix or raw),
        }
    numeric_match = NUMERIC_PIN_RE.search(raw)
    if numeric_match and not RAIL_RE.search(raw):
        return {
            "kind": "component",
            "raw": raw,
            "componentLabel": _clean(plan.get("componentName")) or "Component",
            "pinNumber": numeric_match.group(1),
            "pinLabel": numeric_match.group(2),
            "role": role,
            "function": _infer_pin_function(numeric_match.group(2)),
        }
    if role in {"ground", "power"} or RAIL_RE.search(raw):
        return {"kind": "net", "raw": raw, "role": role, "netName": raw}
    parts = raw.split()
    if len(parts) >= 2:
        return {
            "kind": "component",
            "raw": raw,
            "componentLabel": " ".join(parts[:-1]),
            "pinNumber": None,
            "pinLabel": parts[-1],
            "role": role,
            "function": _infer_pin_function(parts[-1]),
        }
    return {
        "kind": "component",
        "raw": raw,
        "componentLabel": _clean(plan.get("componentName")) or raw,
        "pinNumber": None,
        "pinLabel": raw,
        "role": role,
        "function": _infer_pin_function(raw),
    }


def _connection_confidence(left: dict[str, Any], right: dict[str, Any]) -> float:
    score = 0.55
    for endpoint in (left, right):
        if endpoint["kind"] == "net":
            score += 0.1
        if endpoint.get("pinNumber"):
            score += 0.15
        elif endpoint["kind"] == "component":
            score -= 0.05
    return max(0.2, min(score, 0.95))


def _infer_net_role(text: str) -> str:
    if GROUND_RE.search(text):
        return "ground"
    if POWER_RE.search(text):
        return "power"
    return "signal"


def _infer_pin_function(text: str) -> str:
    role = _infer_net_role(text)
    if role != "signal":
        return role
    lowered = str(text or "").lower()
    if any(word in lowered for word in ("out", "output")):
        return "output"
    if any(word in lowered for word in ("in", "input", "trigger")):
        return "input"
    return "signal"


def _infer_component_type(name: str, detail: str) -> str:
    text = f"{name} {detail}".lower()
    if "resistor" in text or re.search(r"\b\d+\s*(?:ohm|k|m)\b", text):
        return "resistor"
    if "capacitor" in text or re.search(r"\b\d+\s*(?:pf|nf|uf|microfarad)\b", text):
        return "capacitor"
    if "led" in text:
        return "indicator"
    if "transistor" in text:
        return "transistor"
    if "timer" in text or "555" in text or "ic" in text:
        return "integrated_circuit"
    if "supply" in text or "battery" in text:
        return "power_source"
    return "component"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slug(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug[:80] or "unknown"


def _append_unique(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    if item not in items:
        items.append(item)
