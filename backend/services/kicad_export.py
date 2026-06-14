from __future__ import annotations

import base64
import io
import json
import re
import uuid
import zipfile
from typing import Any


KICAD_SCHEMA_VERSION = 1
KICAD_SCH_VERSION = 20230121


def build_kicad_project_package(plan: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    validation = validate_graph_for_kicad(graph)
    project_name = safe_project_name(plan.get("title") or graph.get("title") or "circuitshelf-project")
    if validation["blocking"]:
        return {
            "exportable": False,
            "projectName": project_name,
            "manifest": {
                "schemaVersion": KICAD_SCHEMA_VERSION,
                "projectName": project_name,
                "sourcePlanId": graph.get("planId") or plan.get("id"),
                "files": [],
            },
            "files": [],
            "zipBase64": "",
            "validation": validation,
        }

    files = [
        {
            "path": f"{project_name}.kicad_pro",
            "mimeType": "application/json",
            "content": kicad_project_file(project_name),
        },
        {
            "path": f"{project_name}.kicad_sch",
            "mimeType": "text/plain",
            "content": kicad_schematic_file(project_name, plan, graph),
        },
        {
            "path": "circuit-graph.json",
            "mimeType": "application/json",
            "content": json.dumps(graph, indent=2, sort_keys=True, default=str),
        },
        {
            "path": "README.md",
            "mimeType": "text/markdown",
            "content": readme_file(project_name, plan, graph),
        },
    ]
    manifest = {
        "schemaVersion": KICAD_SCHEMA_VERSION,
        "projectName": project_name,
        "sourcePlanId": graph.get("planId") or plan.get("id"),
        "sourceTitle": graph.get("title") or plan.get("title"),
        "files": [{"path": item["path"], "mimeType": item["mimeType"], "bytes": len(item["content"].encode("utf-8"))} for item in files],
        "componentCount": len(graph.get("components") or []),
        "netCount": len(graph.get("nets") or []),
        "connectionCount": len(graph.get("connections") or []),
    }
    files.append({"path": "manifest.json", "mimeType": "application/json", "content": json.dumps(manifest, indent=2, sort_keys=True)})
    return {
        "exportable": True,
        "projectName": project_name,
        "manifest": manifest,
        "files": files,
        "zipBase64": zip_files_base64(files),
        "validation": validation,
    }


def validate_graph_for_kicad(graph: dict[str, Any]) -> dict[str, Any]:
    findings = list(graph.get("validationFindings") or [])
    blocking = [finding for finding in findings if finding.get("severity") == "blocking"]
    if graph.get("status") != "ready_for_export":
        blocking.append(
            {
                "severity": "blocking",
                "code": "graph_not_ready_for_export",
                "message": "Circuit graph is not ready for KiCad export.",
            }
        )
    if not graph.get("components"):
        blocking.append({"severity": "blocking", "code": "no_components", "message": "No components were found in the circuit graph."})
    if not graph.get("nets"):
        blocking.append({"severity": "blocking", "code": "no_nets", "message": "No nets were found in the circuit graph."})
    if not graph.get("connections"):
        blocking.append({"severity": "blocking", "code": "no_connections", "message": "No connections were found in the circuit graph."})
    for connection in graph.get("connections") or []:
        endpoints = [connection.get("from") or {}, connection.get("to") or {}]
        if not any(endpoint.get("kind") == "pin" and endpoint.get("pinId") for endpoint in endpoints):
            blocking.append(
                {
                    "severity": "blocking",
                    "code": "connection_without_pin",
                    "message": "A KiCad export connection does not include a concrete component pin endpoint.",
                }
            )
    return {
        "blocking": _dedupe_findings(blocking),
        "warnings": [finding for finding in findings if finding.get("severity") == "warning"],
    }


def kicad_project_file(project_name: str) -> str:
    payload = {
        "board": {"design_settings": {"defaults": {}}},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{project_name}.kicad_pro", "version": 1},
        "net_settings": {"classes": [], "meta": {"version": 3}, "net_colors": None},
        "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "", "specctra_dsn": "", "step": "", "vrml": ""}},
        "schematic": {"annotate_start_num": 0, "drawing": {}, "legacy_lib_dir": "", "legacy_lib_list": []},
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def kicad_schematic_file(project_name: str, plan: dict[str, Any], graph: dict[str, Any]) -> str:
    lines = [
        f'(kicad_sch (version {KICAD_SCH_VERSION}) (generator "CircuitShelf")',
        f'  (uuid "{deterministic_uuid(project_name, "schematic")}")',
        '  (paper "A4")',
        "  (title_block",
        f'    (title "{sexpr_escape(graph.get("title") or plan.get("title") or project_name)}")',
        f'    (comment 1 "Generated from CircuitShelf assembly plan {sexpr_escape(str(graph.get("planId") or plan.get("id") or ""))}")',
        "  )",
    ]
    y = 20.0
    lines.append(text_item(f"CircuitShelf graph export: {graph.get('title') or project_name}", 20.0, y, project_name, "title"))
    y += 8.0
    for row in component_rows(graph):
        lines.append(text_item(row, 20.0, y, project_name, row))
        y += 5.0
    y += 4.0
    for row in net_rows(graph):
        lines.append(text_item(row, 20.0, y, project_name, row))
        y += 5.0
    y += 4.0
    for row in connection_rows(graph):
        lines.append(text_item(row, 20.0, y, project_name, row))
        y += 5.0
    lines.append(")")
    return "\n".join(lines) + "\n"


def text_item(text: str, x: float, y: float, project_name: str, key: str) -> str:
    return (
        f'  (text "{sexpr_escape(text[:180])}" (at {x:.2f} {y:.2f} 0)\n'
        '    (effects (font (size 1.27 1.27)) (justify left bottom))\n'
        f'    (uuid "{deterministic_uuid(project_name, key)}")\n'
        "  )"
    )


def component_rows(graph: dict[str, Any]) -> list[str]:
    rows = ["Components:"]
    for ref, component in component_reference_map(graph).items():
        rows.append(f"{ref}: {component.get('label') or component.get('name')} ({component.get('type') or 'component'})")
    return rows


def net_rows(graph: dict[str, Any]) -> list[str]:
    rows = ["Nets:"]
    for net in sorted(graph.get("nets") or [], key=lambda item: str(item.get("name") or item.get("id") or "")):
        rows.append(f"{net.get('name') or net.get('id')}: {net.get('role') or 'signal'}")
    return rows


def connection_rows(graph: dict[str, Any]) -> list[str]:
    pins = {pin.get("id"): pin for pin in graph.get("pins") or []}
    nets = {net.get("id"): net for net in graph.get("nets") or []}
    refs_by_component_id = {component.get("id"): ref for ref, component in component_reference_map(graph).items()}
    rows = ["Connections:"]
    for connection in graph.get("connections") or []:
        left = endpoint_label(connection.get("from") or {}, pins, refs_by_component_id)
        right = endpoint_label(connection.get("to") or {}, pins, refs_by_component_id)
        net = nets.get(connection.get("netId")) or {}
        rows.append(f"{left} -> {right} [{net.get('name') or connection.get('netId')}]")
    return rows


def endpoint_label(endpoint: dict[str, Any], pins: dict[str, dict[str, Any]], refs_by_component_id: dict[str, str]) -> str:
    if endpoint.get("kind") == "net":
        return str(endpoint.get("label") or endpoint.get("netId") or "net")
    pin = pins.get(endpoint.get("pinId")) or {}
    ref = refs_by_component_id.get(pin.get("componentId")) or pin.get("componentLabel") or endpoint.get("componentId") or "component"
    pin_number = pin.get("pinNumber") or "?"
    pin_label = pin.get("label") or endpoint.get("label") or ""
    return f"{ref}.{pin_number} {pin_label}".strip()


def component_reference_map(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    counters: dict[str, int] = {}
    refs: dict[str, dict[str, Any]] = {}
    for component in sorted(graph.get("components") or [], key=lambda item: str(item.get("id") or item.get("label") or "")):
        prefix = reference_prefix(component.get("type") or component.get("label") or "")
        counters[prefix] = counters.get(prefix, 0) + 1
        refs[f"{prefix}{counters[prefix]}"] = component
    return refs


def reference_prefix(component_type: str) -> str:
    value = str(component_type or "").lower()
    if "resistor" in value:
        return "R"
    if "capacitor" in value:
        return "C"
    if "transistor" in value:
        return "Q"
    if "indicator" in value or "diode" in value or "led" in value:
        return "D"
    if "connector" in value or "rail" in value or "power" in value:
        return "J"
    return "U"


def readme_file(project_name: str, plan: dict[str, Any], graph: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {project_name}",
            "",
            "Generated by CircuitShelf from an approved Bench assembly plan circuit graph.",
            "",
            f"- Source plan: {plan.get('title') or graph.get('title')}",
            f"- Components: {len(graph.get('components') or [])}",
            f"- Nets: {len(graph.get('nets') or [])}",
            f"- Connections: {len(graph.get('connections') or [])}",
            "",
            "Open the `.kicad_pro` project in KiCad and review the schematic notes before assigning symbols, footprints, or PCB layout.",
            "Do not fabricate until CircuitShelf fabrication review and KiCad design checks pass.",
            "",
        ]
    )


def zip_files_base64(files: list[dict[str, str]]) -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            info = zipfile.ZipInfo(item["path"])
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, item["content"])
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def safe_project_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip("-")
    return (name[:72] or "circuitshelf-project").lower()


def sexpr_escape(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def deterministic_uuid(project_name: str, key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"circuitshelf:{project_name}:{key}"))


def _dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for finding in findings:
        key = (finding.get("severity"), finding.get("code"), finding.get("message"))
        if key not in seen:
            result.append(finding)
            seen.add(key)
    return result
