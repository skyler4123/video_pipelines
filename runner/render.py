from __future__ import annotations

import fcntl
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .adapters import get_adapter
from .adapters.base import Job
from .config import project_dir
from .errors import AdapterError, RunnerError
from .manifest import (
    build_manifest,
    make_run_id,
    utc_now,
    version_from_output,
    write_manifest,
)
from .plan import Plan, PlannedStage, plan_shot


@contextmanager
def stage_lock(project_id: str, shot_id: str, stage_id: str) -> Iterator[None]:
    path = project_dir(project_id) / "state" / "locks" / f"{shot_id}_{stage_id}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _stage_selection(plan: Plan, stage_id: str | None, all_stages: bool) -> list[PlannedStage]:
    if all_stages:
        stages = plan.selected_stages
    elif stage_id:
        stages = [stage for stage in plan.stages if stage.id == stage_id]
        if not stages:
            raise RunnerError(f"unknown stage {stage_id!r}")
        if not stages[0].enabled:
            raise RunnerError(f"stage {stage_id!r} is disabled")
        stages[0].selected = True
    else:
        stages = plan.selected_stages
        if len(stages) != 1:
            names = ", ".join(stage.id for stage in stages) or "<none>"
            raise RunnerError(
                "choose a stage with --stage, or use --all. "
                f"Enabled stages: {names}"
            )
    return stages


def _cleanup_empty_output(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def render_shot(
    project_id: str,
    shot_id: str,
    *,
    stage_id: str | None = None,
    all_stages: bool = False,
    profile: str | None = None,
    seed: int | None = None,
    set_values: dict[str, Any] | None = None,
    yes: bool = False,
    check_models: bool = False,
) -> tuple[Plan, list[Path]]:
    stage_ids = [stage_id] if stage_id else None
    plan = plan_shot(
        project_id,
        shot_id,
        stage_ids=stage_ids,
        profile_override=profile,
        seed_override=seed,
        set_values=set_values,
        check_models=check_models,
    )
    if plan.errors:
        raise RunnerError("cannot render:\n" + "\n".join(f"  - {e}" for e in plan.errors))

    stages = _stage_selection(plan, stage_id, all_stages)
    for stage in stages:
        if stage.profile == "final" and not yes:
            raise RunnerError(
                "refusing to render the final profile without --yes"
            )
    if all_stages and not yes:
        raise RunnerError("refusing to run all stages without --yes")

    manifests: list[Path] = []
    for stage in stages:
        if stage.errors:
            raise RunnerError(
                f"stage {stage.id} is not renderable:\n"
                + "\n".join(f"  - {e}" for e in stage.errors)
            )
        if stage.profile == "final":
            if plan.shot.status not in {"approved", "final"}:
                raise RunnerError(
                    "the final profile requires shot.status to be 'approved' or "
                    f"'final' (current: {plan.shot.status!r})"
                )
            if not plan.shot.approvals:
                raise RunnerError(
                    "the final profile requires an approval record in shot.yaml"
                )
            if stage.model is not None:
                if not stage.model.license or stage.model.license.lower() in {
                    "unknown",
                    "tbd",
                }:
                    raise RunnerError(
                        f"model {stage.model_id!r} has no verified license; "
                        "final rendering is blocked"
                    )
                if stage.model.source == "local" and not stage.model.sha256:
                    raise RunnerError(
                        f"model {stage.model_id!r} has no sha256 pin; "
                        "final rendering is blocked"
                    )
        if stage.output_path is not None and stage.action == "generate":
            if stage.output_path.exists() and any(stage.output_path.iterdir()):
                raise RunnerError(
                    f"output already exists and will not be overwritten: "
                    f"{stage.output}. Bump the version in shot.yaml."
                )
        run_id = make_run_id(
            project_id,
            shot_id,
            stage.id,
            version_from_output(stage.output),
        )
        started = utc_now()
        output_dir = stage.output_path if stage.action == "generate" else None
        cleanup_dir: Path | None = None
        if output_dir is not None:
            if not output_dir.exists() or (
                output_dir.is_dir() and not any(output_dir.iterdir())
            ):
                cleanup_dir = output_dir
        with stage_lock(project_id, shot_id, stage.id):
            adapter = get_adapter(stage.adapter)
            job = Job(
                run_id=run_id,
                project_id=project_id,
                shot_id=shot_id,
                stage_id=stage.id,
                adapter=stage.adapter,
                action=stage.action,
                profile=stage.profile,
                output_logical=stage.output,
                output_dir=stage.output_path,
                input_paths=stage.input_paths,
                workflow=stage.workflow,
                workflow_path=stage.workflow_path,
                params=stage.params,
                model_id=stage.model_id,
                model=stage.model,
                qc=(
                    plan.shot.qc.model_dump(exclude_none=True)
                    if plan.shot.qc is not None
                    else None
                ),
                metadata={
                    "project": plan.project.id,
                    "shot": plan.shot.id,
                    "stage": stage.id,
                },
            )
            try:
                result = adapter.run(job)
            except AdapterError as exc:
                finished = utc_now()
                _cleanup_empty_output(cleanup_dir)
                manifest = build_manifest(
                    plan,
                    stage,
                    run_id=run_id,
                    started_at=started,
                    finished_at=finished,
                    status="failed",
                    outputs=[],
                    warnings=stage.warnings,
                    errors=[str(exc)],
                    extra={},
                )
                path = write_manifest(project_id, run_id, manifest)
                raise RunnerError(
                    f"stage {stage.id} failed: {exc}\nmanifest: {path}"
                ) from exc

            finished = utc_now()
            manifest = build_manifest(
                plan,
                stage,
                run_id=run_id,
                started_at=started,
                finished_at=finished,
                status=result.status,
                outputs=result.outputs,
                warnings=stage.warnings + result.warnings,
                errors=result.errors,
                extra=result.extra,
            )
            path = write_manifest(project_id, run_id, manifest)
            manifests.append(path)
            if result.status == "failed":
                _cleanup_empty_output(cleanup_dir)
                raise RunnerError(
                    f"stage {stage.id} failed QC or execution:\n"
                    + "\n".join(f"  - {error}" for error in result.errors)
                    + f"\nmanifest: {path}"
                )
    return plan, manifests
