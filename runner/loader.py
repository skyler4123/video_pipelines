from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from .config import (
    PROJECTS_DIR,
    REGISTRY_DIR,
    project_dir,
    resolve_project_path,
)
from .errors import RunnerError
from .models import (
    ModelSpec,
    Pipeline,
    ProfilePreset,
    Project,
    Shot,
    ToolSpec,
    WorkflowMap,
)
from .yamlutil import load_yaml


def _format_validation_error(path: Path, exc: ValidationError) -> RunnerError:
    lines = [f"invalid {path}:"]
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        lines.append(f"  - {location}: {error['msg']}")
    return RunnerError("\n".join(lines))


def load_project(project_id: str) -> Project:
    path = project_dir(project_id) / "project.yaml"
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise RunnerError(f"{path} must contain a YAML object")
    try:
        project = Project.model_validate(data)
    except ValidationError as exc:
        raise _format_validation_error(path, exc) from exc
    if project.id != project_id:
        raise RunnerError(
            f"project id mismatch: directory is {project_id!r}, "
            f"project.yaml says {project.id!r}"
        )
    return project


def load_pipeline(project: Project) -> Pipeline:
    path = project_dir(project.id) / project.defaults.pipeline
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise RunnerError(f"{path} must contain a YAML object")
    try:
        return Pipeline.model_validate(data)
    except ValidationError as exc:
        raise _format_validation_error(path, exc) from exc


def load_shot(project_id: str, shot_id: str) -> Shot:
    path = project_dir(project_id) / "shots" / shot_id / "shot.yaml"
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise RunnerError(f"{path} must contain a YAML object")
    try:
        shot = Shot.model_validate(data)
    except ValidationError as exc:
        raise _format_validation_error(path, exc) from exc
    if shot.id != shot_id:
        raise RunnerError(
            f"shot id mismatch: directory is {shot_id!r}, "
            f"shot.yaml says {shot.id!r}"
        )
    return shot


def load_workflow_map(path: Path) -> WorkflowMap:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise RunnerError(f"{path} must contain a YAML object")
    try:
        return WorkflowMap.model_validate(data)
    except ValidationError as exc:
        raise _format_validation_error(path, exc) from exc


def load_models() -> dict[str, ModelSpec]:
    path = REGISTRY_DIR / "models.yaml"
    data = load_yaml(path) or {}
    if not isinstance(data, dict):
        raise RunnerError(f"{path} must contain a mapping of model id to model")
    try:
        return TypeAdapter(dict[str, ModelSpec]).validate_python(data)
    except ValidationError as exc:
        raise _format_validation_error(path, exc) from exc


def load_tools() -> dict[str, ToolSpec]:
    path = REGISTRY_DIR / "tools.yaml"
    data = load_yaml(path) or {}
    if not isinstance(data, dict):
        raise RunnerError(f"{path} must contain a mapping of tool id to tool")
    try:
        return TypeAdapter(dict[str, ToolSpec]).validate_python(data)
    except ValidationError as exc:
        raise _format_validation_error(path, exc) from exc


def load_presets() -> dict[str, ProfilePreset]:
    path = REGISTRY_DIR / "presets.yaml"
    data = load_yaml(path) or {}
    if not isinstance(data, dict):
        raise RunnerError(f"{path} must contain a mapping of profile to preset")
    try:
        return TypeAdapter(dict[str, ProfilePreset]).validate_python(data)
    except ValidationError as exc:
        raise _format_validation_error(path, exc) from exc


def discover_projects() -> list[str]:
    if not PROJECTS_DIR.exists():
        return []
    return sorted(
        path.name
        for path in PROJECTS_DIR.iterdir()
        if path.is_dir() and not path.name.startswith((".", "_"))
    )


def discover_shots(project_id: str) -> list[str]:
    shots_dir = project_dir(project_id) / "shots"
    if not shots_dir.exists():
        return []
    return sorted(
        path.name
        for path in shots_dir.iterdir()
        if path.is_dir() and (path / "shot.yaml").exists()
    )


def parse_target(target: str | None) -> tuple[str | None, str | None]:
    """Parse `project`, `project/shot`, or a projects/... path."""
    if not target:
        return None, None
    cleaned = target.strip().rstrip("/")
    if cleaned.startswith("projects/"):
        cleaned = cleaned[len("projects/") :]
    parts = [part for part in cleaned.split("/") if part]
    if not parts:
        return None, None
    project_id = parts[0]
    shot_id = None
    if len(parts) >= 2 and parts[1] != "shots":
        shot_id = parts[1]
    elif len(parts) >= 3 and parts[1] == "shots":
        shot_id = parts[2]
    return project_id, shot_id


def shot_dir(project_id: str, shot_id: str) -> Path:
    return project_dir(project_id) / "shots" / shot_id


def resolve_shot_path(project_id: str, logical_path: str) -> Path:
    return resolve_project_path(project_id, logical_path)
