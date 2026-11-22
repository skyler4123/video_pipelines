from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import display_path, models_dir, resolve_project_path
from .constraints import check_constraints
from .errors import RunnerError
from .loader import load_pipeline, load_project, load_shot, load_workflow_map
from .models import ModelSpec, Pipeline, Project, Shot, Stage
from .registry import Registry
from .workflow import (
    apply_params,
    load_workflow,
    topology_hash,
    validate_api_workflow,
    validate_mapping,
)


@dataclass
class PlannedStage:
    id: str
    adapter: str
    action: str
    enabled: bool
    selected: bool
    profile: str
    model_id: str | None
    model: ModelSpec | None
    workflow_file: str | None
    map_file: str | None
    workflow_path: Path | None
    output: str | None
    output_path: Path | None
    input_paths: list[Path] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    applied: dict[str, Any] = field(default_factory=dict)
    workflow: dict[str, Any] | None = None
    workflow_sha256: str | None = None
    topology_sha256: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "adapter": self.adapter,
            "action": self.action,
            "enabled": self.enabled,
            "selected": self.selected,
            "profile": self.profile,
            "model": self.model_id,
            "workflow": self.workflow_file,
            "map": self.map_file,
            "output": self.output,
            "output_path": display_path(self.output_path) if self.output_path else None,
            "input_paths": [display_path(path) for path in self.input_paths],
            "params": self.params,
            "applied": self.applied,
            "workflow_sha256": self.workflow_sha256,
            "topology_sha256": self.topology_sha256,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class Plan:
    project: Project
    shot: Shot
    pipeline: Pipeline
    profile: str
    stages: list[PlannedStage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def selected_stages(self) -> list[PlannedStage]:
        return [stage for stage in self.stages if stage.selected]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project.id,
            "shot": self.shot.id,
            "profile": self.profile,
            "stages": [stage.to_dict() for stage in self.stages],
            "warnings": self.warnings,
            "errors": self.errors,
        }


def coerce_scalar(value: str) -> Any:
    try:
        parsed = yaml.safe_load(value)
    except yaml.YAMLError:
        return value
    return parsed


def parse_set_values(values: list[str] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in values or []:
        if "=" not in item:
            raise RunnerError(f"--set expects key=value, got {item!r}")
        key, raw = item.split("=", 1)
        key = key.strip()
        if not key:
            raise RunnerError(f"--set has an empty key: {item!r}")
        result[key] = coerce_scalar(raw.strip())
    return result


def _model_path(model: ModelSpec) -> Path | None:
    if not model.path:
        return None
    path = model.path
    root = models_dir()
    if root is not None:
        path = path.replace("${MODELS_DIR}", str(root)).replace("$MODELS_DIR", str(root))
    path = os.path.expanduser(path)
    return Path(path)


def _output_has_files(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    if path.is_file():
        return True
    return any(path.iterdir())


def plan_shot(
    project_id: str,
    shot_id: str,
    *,
    stage_ids: list[str] | None = None,
    profile_override: str | None = None,
    seed_override: int | None = None,
    set_values: dict[str, Any] | None = None,
    check_models: bool = False,
    registry: Registry | None = None,
) -> Plan:
    project = load_project(project_id)
    pipeline = load_pipeline(project)
    shot = load_shot(project_id, shot_id)
    registry = registry or Registry.load()

    all_stage_ids = {stage.id for stage in pipeline.stages}
    for stage_id in stage_ids or []:
        if stage_id not in all_stage_ids:
            raise RunnerError(
                f"unknown stage {stage_id!r} for project {project_id!r}; "
                f"available stages: {', '.join(sorted(all_stage_ids))}"
            )

    effective_profile = (
        profile_override
        or shot.render.profile
        or project.defaults.profile
    )
    plan = Plan(
        project=project,
        shot=shot,
        pipeline=pipeline,
        profile=effective_profile,
    )

    output_by_stage: dict[str, Path | None] = {}
    enabled_by_stage: dict[str, bool] = {}
    last_enabled_output: Path | None = None

    for index, stage in enumerate(pipeline.stages):
        selected = stage_ids is None and stage.enabled
        if stage_ids is not None:
            selected = stage.id in stage_ids
        if selected and not stage.enabled:
            plan.errors.append(f"stage {stage.id!r} is disabled")

        override = shot.stages.get(stage.id)
        profile = (
            profile_override
            or (override.profile if override else None)
            or shot.render.profile
            or project.defaults.profile
        )
        model_id = (override.model if override else None) or stage.model
        model = registry.models.get(model_id) if model_id else None
        stage_workflow = (override.workflow if override else None) or stage.workflow
        stage_map = (override.map if override else None) or stage.map

        planned = PlannedStage(
            id=stage.id,
            adapter=stage.adapter,
            action=stage.action,
            enabled=stage.enabled,
            selected=selected,
            profile=profile,
            model_id=model_id,
            model=model,
            workflow_file=stage_workflow,
            map_file=stage_map,
            workflow_path=(
                resolve_project_path(project_id, stage_workflow)
                if stage_workflow
                else None
            ),
            output=None,
            output_path=None,
        )

        if model_id and model is None:
            planned.errors.append(
                f"model {model_id!r} is not in registry/models.yaml"
            )
        if model is not None:
            if not model.license or model.license.lower() in {"unknown", "tbd"}:
                planned.warnings.append(
                    f"model {model_id!r} has no verified license"
                )
            if check_models and model.source == "local":
                path = _model_path(model)
                if path is None or not path.exists():
                    planned.warnings.append(
                        f"local model path is missing: {path or model.path!r}"
                    )
            if model.source == "local" and model.sha256 in (None, "", "TBD"):
                planned.warnings.append(
                    f"model {model_id!r} has no sha256 pin"
                )

        # Resolve the preset for this profile.
        preset: dict[str, Any] = {}
        if model is not None:
            if profile in model.presets:
                preset = copy.deepcopy(model.presets[profile])
            elif model.presets:
                planned.errors.append(
                    f"model {model_id!r} has no preset named {profile!r}"
                )
        if not preset and profile in registry.presets:
            preset = copy.deepcopy(registry.presets[profile].params)
        params = preset
        if override is not None:
            params.update(copy.deepcopy(override.params))
        if set_values:
            params.update(copy.deepcopy(set_values))

        if stage.action == "generate":
            params["prompt.positive"] = shot.prompt.positive
            params["prompt.negative"] = shot.prompt.negative

            seed = seed_override
            if seed is None and override is not None:
                seed = override.seed
            if seed is None:
                seed = shot.render.seed
            if seed is not None:
                params["sampler.seed"] = seed

        output = override.output if override is not None else None
        if stage.action == "generate" and not output:
            if stage.enabled:
                planned.errors.append(
                    f"stage {stage.id!r} needs an output path "
                    f"(for example assets/{shot_id}/{stage.id}/v001)"
                )
        if output:
            planned.output = output
            try:
                planned.output_path = resolve_project_path(project_id, output)
            except RunnerError as exc:
                planned.errors.append(str(exc))
            version = output.rstrip("/").rsplit("/", 1)[-1]
            params["output.prefix"] = f"{project_id}/{shot_id}/{stage.id}/{version}"
            if _output_has_files(planned.output_path):
                planned.warnings.append(
                    f"output already exists and will not be overwritten: {output}"
                )

        # Resolve inputs from declared dependencies or the previous stage.
        input_paths: list[Path] = []
        dependencies = stage.depends_on or (
            [pipeline.stages[index - 1].id] if index > 0 else []
        )
        for dependency in dependencies:
            dependency_output = output_by_stage.get(dependency)
            if dependency_output is None or not enabled_by_stage.get(dependency, False):
                if stage.enabled:
                    planned.errors.append(
                        f"stage {stage.id!r} depends on {dependency!r}, "
                        "which has no enabled output"
                    )
            else:
                input_paths.append(dependency_output)
        if not dependencies and last_enabled_output is not None:
            input_paths.append(last_enabled_output)

        # Reference inputs are explicit in shot.yaml only.
        for name, ref in shot.refs.items():
            try:
                ref_path = resolve_project_path(project_id, ref)
            except RunnerError as exc:
                planned.errors.append(f"ref {name!r}: {exc}")
                continue
            if not ref_path.exists():
                planned.warnings.append(
                    f"ref {name!r} is missing: {display_path(ref_path)}"
                )
            input_paths.append(ref_path)
        planned.input_paths = input_paths

        planned.params = params

        # Load and parameterize the workflow.
        if planned.workflow_path is not None:
            if not planned.workflow_path.exists():
                planned.errors.append(
                    f"workflow is missing: {display_path(planned.workflow_path)}"
                )
            else:
                try:
                    workflow = load_workflow(planned.workflow_path)
                    planned.workflow = workflow
                    planned.workflow_sha256 = _sha256_bytes(
                        planned.workflow_path.read_bytes()
                    )
                    planned.topology_sha256 = topology_hash(workflow)
                except RunnerError as exc:
                    planned.errors.append(str(exc))
                else:
                    planned.errors.extend(validate_api_workflow(workflow))
                    if stage_map:
                        map_path = resolve_project_path(project_id, stage_map)
                        planned.map_file = stage_map
                        if not map_path.exists():
                            planned.errors.append(
                                f"workflow map is missing: {display_path(map_path)}"
                            )
                        else:
                            try:
                                mapping = load_workflow_map(map_path)
                            except RunnerError as exc:
                                planned.errors.append(str(exc))
                            else:
                                planned.errors.extend(
                                    validate_mapping(workflow, mapping)
                                )
                                applied_workflow, applied, warnings, errors = (
                                    apply_params(workflow, mapping, params)
                                )
                                planned.workflow = applied_workflow
                                planned.applied = applied
                                if stage.enabled:
                                    planned.warnings.extend(warnings)
                                planned.errors.extend(errors)
                    else:
                        planned.warnings.append(
                            f"stage {stage.id!r} has a workflow but no map"
                        )
        elif stage.action == "generate" and stage.adapter == "comfyui":
            planned.errors.append(
                f"comfyui stage {stage.id!r} needs a workflow"
            )

        if stage.action == "generate" and model is None and stage.adapter != "mock":
            planned.errors.append(f"stage {stage.id!r} needs a model")

        if model is not None:
            constraint_errors, constraint_warnings = check_constraints(model, params)
            planned.errors.extend(constraint_errors)
            planned.warnings.extend(constraint_warnings)

        if stage.adapter == "mock" and profile == "final":
            planned.errors.append(
                "the mock adapter cannot be used with the final profile"
            )

        if stage.adapter == "ffmpeg" and stage.action == "qc":
            if not planned.input_paths:
                planned.errors.append(
                    f"QC stage {stage.id!r} has no input to inspect"
                )

        if stage.adapter not in registry.tools:
            planned.warnings.append(
                f"adapter {stage.adapter!r} is not listed in registry/tools.yaml"
            )

        planned.errors = list(dict.fromkeys(planned.errors))
        planned.warnings = list(dict.fromkeys(planned.warnings))

        plan.stages.append(planned)
        output_by_stage[stage.id] = planned.output_path
        enabled_by_stage[stage.id] = stage.enabled
        if stage.enabled and planned.output_path is not None:
            last_enabled_output = planned.output_path

        if selected:
            plan.errors.extend(planned.errors)
        else:
            plan.warnings.extend(
                f"stage {stage.id}: {error}" for error in planned.errors
            )
        plan.warnings.extend(
            f"stage {stage.id}: {warning}" for warning in planned.warnings
        )

    if not plan.selected_stages:
        plan.errors.append("no enabled stages selected")

    plan.errors = list(dict.fromkeys(plan.errors))
    plan.warnings = list(dict.fromkeys(plan.warnings))
    return plan


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
