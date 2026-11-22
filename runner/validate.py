from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .config import REPO_ROOT, display_path, project_dir, resolve_project_path
from .errors import RunnerError
from .loader import (
    discover_projects,
    discover_shots,
    load_pipeline,
    load_project,
    load_shot,
    load_workflow_map,
    parse_target,
)
from .models import Pipeline, Project, Shot
from .plan import plan_shot
from .registry import Registry
from .workflow import load_workflow, validate_api_workflow, validate_mapping
from .yamlutil import load_json, load_yaml, walk_strings

MEDIA_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".wav",
    ".mp3",
    ".flac",
    ".safetensors",
    ".gguf",
    ".ckpt",
    ".pth",
    ".bin",
}
TEXT_EXTENSIONS = {
    ".yaml",
    ".yml",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
VERSIONED_OUTPUT_RE = re.compile(
    r"^assets/(?P<shot>[a-z][a-z0-9_]{1,31})/(?P<stage>[a-z][a-z0-9_]{1,31})/v(?P<version>\d{3,})$"
)


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_projects: int = 0
    checked_shots: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def _is_absolute_like(value: str) -> bool:
    if value.startswith("$HOME"):
        return True
    if value.startswith(("http://", "https://", "git@", "${")):
        return False
    if value.startswith("$"):
        return False
    if value.startswith(("/", "~")):
        return True
    return bool(re.match(r"^[A-Za-z]:[\\/]", value))


def _check_string_paths(
    data: Any,
    source: Path,
    report: ValidationReport,
    *,
    skip_keys: Iterable[str] = ("notes", "description", "title"),
) -> None:
    for path, value in walk_strings(data):
        leaf = path.rsplit(".", 1)[-1] if "." in path else path
        if leaf in skip_keys:
            continue
        if _is_absolute_like(value):
            report.error(f"{display_path(source)}:{path}: absolute path is not allowed")
        if value.startswith("projects/"):
            report.error(
                f"{display_path(source)}:{path}: cross-project reference is not allowed"
            )
        if ".." in Path(value).parts and not value.startswith(("http://", "https://")):
            report.error(
                f"{display_path(source)}:{path}: parent path segments are not allowed"
            )


def _check_project_files(project: Project, report: ValidationReport) -> None:
    root = project_dir(project.id)
    candidates = [root / "project.yaml", root / project.defaults.pipeline]
    shots_dir = root / "shots"
    if shots_dir.exists():
        for shot_file in shots_dir.glob("*/shot.yaml"):
            candidates.append(shot_file)
    stages_dir = root / "stages"
    if stages_dir.exists():
        candidates.extend(stages_dir.rglob("*.yaml"))
        candidates.extend(stages_dir.rglob("*.yml"))
        candidates.extend(stages_dir.rglob("*.json"))
        candidates.extend(stages_dir.rglob("*.api.json"))
        candidates.extend(stages_dir.rglob("*.map.yaml"))
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        try:
            if path.suffix == ".json":
                data = load_json(path)
            else:
                data = load_yaml(path)
        except RunnerError as exc:
            report.error(str(exc))
            continue
        _check_string_paths(data, path, report)


def _check_pipeline(
    project: Project, pipeline: Pipeline, registry: Registry, report: ValidationReport
) -> None:
    for stage in pipeline.stages:
        label = f"{project.id}: stage {stage.id}"
        if stage.adapter not in registry.tools:
            report.warning(f"{label}: adapter {stage.adapter!r} is not in registry/tools.yaml")
        if stage.model and stage.model not in registry.models:
            report.error(f"{label}: model {stage.model!r} is not in registry/models.yaml")
        if stage.action == "generate" and not stage.model and stage.adapter != "mock":
            report.error(f"{label}: generate stage has no model")
        if stage.enabled and stage.adapter == "comfyui":
            if not stage.workflow:
                report.error(f"{label}: comfyui stage has no workflow")
            if not stage.map:
                report.error(f"{label}: comfyui stage has no workflow map")
        if stage.workflow:
            workflow_path = resolve_project_path(project.id, stage.workflow)
            if not workflow_path.exists():
                message = f"{label}: workflow is missing: {stage.workflow}"
                if stage.enabled:
                    report.error(message)
                else:
                    report.warning(message)
            else:
                try:
                    workflow = load_workflow(workflow_path)
                except RunnerError as exc:
                    report.error(f"{label}: {exc}")
                else:
                    for error in validate_api_workflow(workflow):
                        report.error(f"{label}: {error}")
                    if stage.map:
                        map_path = resolve_project_path(project.id, stage.map)
                        if not map_path.exists():
                            message = f"{label}: workflow map is missing: {stage.map}"
                            if stage.enabled:
                                report.error(message)
                            else:
                                report.warning(message)
                        else:
                            try:
                                mapping = load_workflow_map(map_path)
                            except RunnerError as exc:
                                report.error(f"{label}: {exc}")
                            else:
                                for error in validate_mapping(workflow, mapping):
                                    report.error(f"{label}: {error}")
        if stage.map and not stage.workflow:
            report.warning(f"{label}: map is set but workflow is empty")


def _check_shot(
    project: Project,
    pipeline: Pipeline,
    shot: Shot,
    registry: Registry,
    report: ValidationReport,
) -> None:
    label = f"{project.id}/{shot.id}"
    pipeline_ids = {stage.id for stage in pipeline.stages}
    for stage_id in shot.stages:
        if stage_id not in pipeline_ids:
            report.error(f"{label}: shot references unknown stage {stage_id!r}")

    if not shot.prompt.positive.strip():
        report.error(f"{label}: prompt.positive is empty")

    for name, ref in shot.refs.items():
        if not (ref.startswith("refs/") or ref.startswith("shared/")):
            report.error(
                f"{label}: ref {name!r} must live under refs/ or shared/, got {ref!r}"
            )
        try:
            ref_path = resolve_project_path(project.id, ref)
        except RunnerError as exc:
            report.error(f"{label}: ref {name!r}: {exc}")
            continue
        if not ref_path.exists():
            report.error(f"{label}: ref {name!r} is missing: {ref}")
        else:
            try:
                head = ref_path.read_bytes()[:100]
            except OSError:
                head = b""
            if head.startswith(b"version https://git-lfs.github.com/spec/v1"):
                report.warning(
                    f"{label}: ref {name!r} is a Git LFS pointer; run `git lfs pull`"
                )

    for stage in pipeline.stages:
        override = shot.stages.get(stage.id)
        output = override.output if override else None
        if not output:
            if stage.enabled and stage.action == "generate":
                report.error(
                    f"{label}: enabled stage {stage.id!r} needs a versioned output path"
                )
            continue
        match = VERSIONED_OUTPUT_RE.fullmatch(output)
        if not match:
            report.error(
                f"{label}: stage {stage.id!r} output must match "
                f"assets/{shot.id}/{stage.id}/vNNN, got {output!r}"
            )
        elif match.group("shot") != shot.id or match.group("stage") != stage.id:
            report.error(
                f"{label}: stage {stage.id!r} output must be under "
                f"assets/{shot.id}/{stage.id}/vNNN, got {output!r}"
            )

    if shot.qc is not None and not any(
        stage.action == "qc" and stage.enabled for stage in pipeline.stages
    ):
        report.warning(f"{label}: qc is defined but the pipeline has no enabled QC stage")

    try:
        plan = plan_shot(project.id, shot.id, registry=registry)
    except RunnerError as exc:
        report.error(f"{label}: {exc}")
    else:
        for error in plan.errors:
            report.error(f"{label}: {error}")
        for warning in plan.warnings:
            if any(existing in warning for existing in report.warnings):
                continue
            report.warning(f"{label}: {warning}")

        if shot.qc is not None:
            qc_dependencies: set[str] = set()
            enabled_stages = [stage for stage in pipeline.stages if stage.enabled]
            for index, stage in enumerate(enabled_stages):
                if stage.action != "qc":
                    continue
                if stage.depends_on:
                    qc_dependencies.update(stage.depends_on)
                elif index > 0:
                    qc_dependencies.add(enabled_stages[index - 1].id)
            for planned in plan.stages:
                if planned.id not in qc_dependencies or not planned.enabled:
                    continue
                if planned.action != "generate":
                    continue
                for prefix in ("image", "video"):
                    width = planned.params.get(f"{prefix}.width")
                    height = planned.params.get(f"{prefix}.height")
                    if (
                        width is not None
                        and height is not None
                        and shot.qc.width is not None
                        and shot.qc.height is not None
                        and (width != shot.qc.width or height != shot.qc.height)
                    ):
                        report.warning(
                            f"{label}: QC expects {shot.qc.width}x{shot.qc.height}, "
                            f"but stage {planned.id!r} renders {width}x{height}"
                        )

    if shot.status in {"approved", "final"}:
        if not shot.approvals:
            report.error(f"{label}: status {shot.status!r} requires an approval record")
        for approval in shot.approvals:
            manifest_path = project_dir(project.id) / "runs" / f"{approval.run_id}.yaml"
            if not manifest_path.exists():
                report.error(
                    f"{label}: approval run manifest is missing: {approval.run_id}"
                )
                continue
            try:
                manifest = load_yaml(manifest_path)
            except RunnerError as exc:
                report.error(f"{label}: {exc}")
                continue
            if not isinstance(manifest, dict):
                report.error(f"{label}: run manifest is not an object: {approval.run_id}")
                continue
            if manifest.get("status") != "succeeded":
                report.error(
                    f"{label}: approval run {approval.run_id} did not succeed"
                )
            if manifest.get("simulated"):
                report.error(
                    f"{label}: approval run {approval.run_id} is simulated and "
                    "cannot approve real output"
                )
            if approval.sha256:
                hashes = {
                    output.get("sha256")
                    for output in manifest.get("outputs", [])
                    if isinstance(output, dict)
                }
                if approval.sha256 not in hashes:
                    report.error(
                        f"{label}: approval sha256 does not match run "
                        f"{approval.run_id}"
                    )


def _check_git(report: ValidationReport) -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        report.warning("git is unavailable; media and secret checks were skipped")
        return
    paths = [path for path in result.stdout.decode("utf-8", errors="replace").split("\0") if path]
    for relative in paths:
        path = REPO_ROOT / relative
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in MEDIA_EXTENSIONS:
            size = path.stat().st_size
            if (
                "/refs/" in f"/{relative}" or relative.startswith("shared/")
            ) and size <= 10 * 1024 * 1024:
                continue
            if relative.startswith("docs/") and size <= 2 * 1024 * 1024:
                continue
            report.error(
                f"tracked media is not allowed: {relative} "
                "(use refs/ or shared/ with LFS, or an external store)"
            )
        if relative.startswith(("projects/", "models/")) and any(
            part in {"assets", "deliverables", "state"} for part in Path(relative).parts
        ):
            report.error(f"tracked working media/state is not allowed: {relative}")
        if path.name == ".env" or (
            path.name.startswith(".env.") and path.name != ".env.example"
        ):
            report.error(f"tracked secret file is not allowed: {relative}")
        if suffix not in TEXT_EXTENSIONS or path.stat().st_size > 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                report.error(f"possible secret in tracked file: {relative}")
                break


def _check_registry(registry: Registry, report: ValidationReport) -> None:
    for model_id, model in registry.models.items():
        if not model.license or model.license.lower() in {"unknown", "tbd"}:
            report.warning(f"model {model_id!r} has no verified license")
        if model.source == "local" and not model.sha256:
            report.warning(f"model {model_id!r} has no sha256 pin")
    comfy = registry.tools.get("comfyui")
    if comfy is not None:
        if not comfy.image:
            report.warning(
                "registry/tools.yaml: comfyui has no pinned image digest"
            )
        elif comfy.image.endswith(":latest"):
            report.warning(
                "registry/tools.yaml: comfyui image uses :latest; pin a digest"
            )


def validate(
    target: str | None = None,
    *,
    no_git: bool = False,
    registry: Registry | None = None,
) -> ValidationReport:
    report = ValidationReport()
    registry = registry or Registry.load()
    _check_registry(registry, report)

    project_id, shot_id = parse_target(target)
    projects = discover_projects()
    if project_id and project_id not in projects:
        report.error(f"unknown project: {project_id}")
        return report
    if not projects:
        report.warning("no projects found under projects/")

    for current_id in projects:
        if project_id and current_id != project_id:
            continue
        try:
            project = load_project(current_id)
            pipeline = load_pipeline(project)
        except RunnerError as exc:
            report.error(f"{current_id}: {exc}")
            continue
        report.checked_projects += 1
        _check_project_files(project, report)
        _check_pipeline(project, pipeline, registry, report)

        shots = discover_shots(current_id)
        if not shots:
            report.warning(f"{current_id}: no shots found")
        for current_shot in shots:
            if shot_id and current_shot != shot_id:
                continue
            try:
                shot = load_shot(current_id, current_shot)
            except RunnerError as exc:
                report.error(f"{current_id}/{current_shot}: {exc}")
                continue
            report.checked_shots += 1
            _check_shot(project, pipeline, shot, registry, report)

        if shot_id and shot_id not in shots:
            report.error(f"unknown shot {shot_id!r} in project {current_id!r}")

    if not no_git:
        _check_git(report)
    report.errors = list(dict.fromkeys(report.errors))
    report.warnings = list(dict.fromkeys(report.warnings))
    return report
