from __future__ import annotations

import base64
import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

from backend.services.kicad_export import build_kicad_project_package, zip_files_base64


Runner = Callable[[list[str], Path, Path], None]


def build_fabrication_package(
    plan: dict[str, Any],
    graph: dict[str, Any],
    *,
    kicad_cli_path: str | None = None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    kicad_package = build_kicad_project_package(plan, graph)
    project_name = kicad_package["projectName"]
    manifest = {
        "schemaVersion": 1,
        "projectName": project_name,
        "sourcePlanId": graph.get("planId") or plan.get("id"),
        "status": "pending",
        "downloadAllowed": False,
        "requiredNextStep": "",
        "files": [],
        "checks": [],
    }
    if not kicad_package.get("exportable"):
        manifest["status"] = "blocked"
        manifest["requiredNextStep"] = "Resolve circuit graph validation findings before KiCad or fabrication export."
        manifest["checks"].append({"status": "blocking", "code": "kicad_project_not_exportable", "message": "KiCad project package is not exportable."})
        return package_result(False, manifest, [], kicad_package)

    pcb_file = find_file(kicad_package.get("files") or [], ".kicad_pcb")
    if not pcb_file:
        manifest["status"] = "needs_layout"
        manifest["requiredNextStep"] = "Open the KiCad project, create/review a PCB layout, then rerun fabrication export."
        manifest["checks"].append({"status": "blocking", "code": "pcb_layout_missing", "message": "No KiCad PCB layout file is available yet."})
        manifest["files"].append({"path": f"{project_name}-kicad-project.zip", "kind": "kicad_project", "bytes": len(kicad_package.get("zipBase64") or "")})
        return package_result(False, manifest, [], kicad_package)

    cli = kicad_cli_path or shutil.which("kicad-cli")
    if not cli:
        manifest["status"] = "tool_unavailable"
        manifest["requiredNextStep"] = "Install KiCad command-line tools and rerun fabrication export."
        manifest["checks"].append({"status": "blocking", "code": "kicad_cli_missing", "message": "kicad-cli is required to export Gerber and drill files."})
        manifest["files"].append({"path": f"{project_name}-kicad-project.zip", "kind": "kicad_project", "bytes": len(kicad_package.get("zipBase64") or "")})
        return package_result(False, manifest, [], kicad_package)

    with tempfile.TemporaryDirectory(prefix="circuitshelf-fab-") as tmp:
        root = Path(tmp)
        project_dir = root / project_name
        output_dir = root / "fabrication"
        project_dir.mkdir()
        output_dir.mkdir()
        write_kicad_files(project_dir, kicad_package.get("files") or [])
        pcb_path = project_dir / pcb_file["path"]
        run = runner or run_kicad_cli
        try:
            run([cli, "pcb", "export", "gerbers", "--output", str(output_dir), str(pcb_path)], project_dir, output_dir)
            run([cli, "pcb", "export", "drill", "--output", str(output_dir), str(pcb_path)], project_dir, output_dir)
        except Exception as exc:
            manifest["status"] = "failed"
            manifest["requiredNextStep"] = "Fix the KiCad PCB project and rerun fabrication export."
            manifest["checks"].append({"status": "blocking", "code": "kicad_cli_failed", "message": str(exc)[:500]})
            manifest["files"].append({"path": f"{project_name}-kicad-project.zip", "kind": "kicad_project", "bytes": len(kicad_package.get("zipBase64") or "")})
            return package_result(False, manifest, [], kicad_package)

        fabrication_files = collect_output_files(output_dir)
        if not fabrication_files:
            manifest["status"] = "failed"
            manifest["requiredNextStep"] = "Review the KiCad export output and rerun fabrication export."
            manifest["checks"].append({"status": "blocking", "code": "fabrication_files_missing", "message": "KiCad export completed without Gerber or drill files."})
            return package_result(False, manifest, [], kicad_package)

    manifest["status"] = "generated"
    manifest["downloadAllowed"] = True
    manifest["requiredNextStep"] = "Review fabrication files before sending them to a PCB manufacturer."
    manifest["checks"].append({"status": "pass", "code": "fabrication_files_generated", "message": "Gerber/drill output files were generated."})
    manifest["files"] = [
        {"path": item["path"], "kind": item["kind"], "bytes": len(base64.b64decode(item["base64"]))}
        for item in fabrication_files
    ]
    manifest["files"].append({"path": f"{project_name}-kicad-project.zip", "kind": "kicad_project", "bytes": len(kicad_package.get("zipBase64") or "")})
    return package_result(True, manifest, fabrication_files, kicad_package)


def package_result(generated: bool, manifest: dict[str, Any], files: list[dict[str, str]], kicad_package: dict[str, Any]) -> dict[str, Any]:
    package_files = [
        {"path": item["path"], "mimeType": item["mimeType"], "content": item["content"]}
        for item in kicad_package.get("files") or []
    ]
    package_files.append({"path": "fabrication-manifest.json", "mimeType": "application/json", "content": _json_manifest(manifest)})
    for item in files:
        package_files.append({"path": item["path"], "mimeType": item["mimeType"], "content": base64.b64decode(item["base64"]).decode("latin1")})
    return {
        "generated": generated,
        "status": manifest["status"],
        "manifest": manifest,
        "kicadProject": kicad_package,
        "files": files,
        "zipBase64": zip_files_base64(package_files),
    }


def find_file(files: list[dict[str, Any]], suffix: str) -> dict[str, Any] | None:
    for item in files:
        if str(item.get("path") or "").endswith(suffix):
            return item
    return None


def write_kicad_files(project_dir: Path, files: list[dict[str, Any]]) -> None:
    for item in files:
        path = project_dir / str(item.get("path") or "")
        if not path.name:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(item.get("content") or ""), encoding="utf-8")


def run_kicad_cli(command: list[str], _project_dir: Path, _output_dir: Path) -> None:
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
    if completed.returncode:
        message = completed.stderr.strip() or completed.stdout.strip() or f"kicad-cli exited with {completed.returncode}"
        raise RuntimeError(message)


def collect_output_files(output_dir: Path) -> list[dict[str, str]]:
    files = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        kind = "drill" if suffix in {".drl", ".xln"} else "gerber" if suffix.startswith(".g") else "fabrication"
        data = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "kind": kind,
                "mimeType": "application/octet-stream",
                "base64": base64.b64encode(data).decode("ascii"),
            }
        )
    return files


def _json_manifest(manifest: dict[str, Any]) -> str:
    import json

    return json.dumps(manifest, indent=2, sort_keys=True)
