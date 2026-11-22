from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import display_path, project_dir
from .plan import Plan, PlannedStage
from .workflow import sha256_file
from .yamlutil import write_yaml


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id(project_id: str, shot_id: str, stage_id: str, version: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(3)
    return f"{stamp}_{project_id}_{shot_id}_{stage_id}_{version}_{suffix}"


def version_from_output(output: str | None) -> str:
    if not output:
        return "v000"
    name = output.rstrip("/").rsplit("/", 1)[-1]
    return name if name.startswith("v") else "v000"


def _hash_path(path: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {"path": display_path(path)}
    if path.is_file():
        entry["sha256"] = sha256_file(path)
        entry["bytes"] = path.stat().st_size
    elif path.is_dir():
        entry["type"] = "directory"
        files = []
        for child in sorted(path.rglob("*")):
            if child.is_file():
                files.append(
                    {
                        "path": display_path(child),
                        "sha256": sha256_file(child),
                        "bytes": child.stat().st_size,
                    }
                )
        entry["files"] = files
    else:
        entry["missing"] = True
    return entry


def build_manifest(
    plan: Plan,
    stage: PlannedStage,
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    status: str,
    outputs: list[Path],
    warnings: list[str],
    errors: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extra = extra or {}
    model_info: dict[str, Any] | None = None
    if stage.model is not None:
        model_info = {
            "id": stage.model_id,
            "kind": stage.model.kind,
            "source": stage.model.source,
            "license": stage.model.license,
            "sha256": stage.model.sha256,
        }
    workflow_info = None
    if stage.workflow_path is not None:
        workflow_info = {
            "file": stage.workflow_file,
            "sha256": stage.workflow_sha256,
            "topology_sha256": stage.topology_sha256,
        }
    return {
        "manifest_version": 1,
        "run_id": run_id,
        "project": plan.project.id,
        "shot": plan.shot.id,
        "stage": stage.id,
        "status": status,
        "simulated": bool(extra.get("simulated")),
        "profile": stage.profile,
        "adapter": stage.adapter,
        "action": stage.action,
        "model": model_info,
        "workflow": workflow_info,
        "output": stage.output,
        "params": stage.params,
        "inputs": [_hash_path(path) for path in stage.input_paths],
        "outputs": [_hash_path(path) for path in outputs],
        "qc": extra.get("qc"),
        "tool": {
            key: value
            for key, value in extra.items()
            if key in {"prompt_id", "client_id", "skipped_reason"}
        },
        "warnings": warnings,
        "errors": errors,
        "started_at": started_at,
        "finished_at": finished_at,
    }


def write_manifest(project_id: str, run_id: str, manifest: dict[str, Any]) -> Path:
    root = project_dir(project_id)
    path = root / "runs" / f"{run_id}.yaml"
    write_yaml(path, manifest)
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    with (state / "runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, sort_keys=True) + "\n")
    return path
