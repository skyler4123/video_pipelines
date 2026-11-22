from __future__ import annotations

import os
from pathlib import Path

from .errors import RunnerError

REPO_ROOT = Path(
    os.environ.get(
        "VIDEO_PIPELINES_ROOT",
        Path(__file__).resolve().parent.parent,
    )
).expanduser().resolve()
PROJECTS_DIR = REPO_ROOT / "projects"
REGISTRY_DIR = REPO_ROOT / "registry"
SCHEMAS_DIR = REPO_ROOT / "schemas"
TEMPLATES_DIR = REPO_ROOT / "templates"


def media_root() -> Path | None:
    value = os.environ.get("MEDIA_ROOT")
    if not value:
        return None
    return Path(value).expanduser().resolve()


def models_dir() -> Path | None:
    value = os.environ.get("MODELS_DIR")
    if not value:
        return None
    return Path(value).expanduser().resolve()


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def resolve_project_path(project_id: str, logical_path: str) -> Path:
    """Resolve a project-relative logical path.

    `assets/...` and `deliverables/...` are resolved against MEDIA_ROOT when it
    is configured, otherwise against the project directory. Everything else
    (refs, stages, runs, state) stays inside the project directory.
    """
    if not logical_path:
        raise RunnerError("empty path")
    if logical_path.startswith(("/", "~")) or ":" in logical_path.split("/", 1)[0]:
        raise RunnerError(f"absolute paths are not allowed: {logical_path!r}")
    if ".." in Path(logical_path).parts:
        raise RunnerError(f"parent path segments are not allowed: {logical_path!r}")

    base = project_dir(project_id)
    if logical_path.startswith("shared/"):
        base = REPO_ROOT
    elif logical_path.startswith(("assets/", "deliverables/")):
        root = media_root()
        if root is not None:
            base = root / project_id

    resolved = (base / logical_path).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError as exc:
        raise RunnerError(
            f"path escapes its project/media root: {logical_path!r}"
        ) from exc
    return resolved


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
