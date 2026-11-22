from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .adapters.comfyui import ComfyUIAdapter
from .config import PROJECTS_DIR, TEMPLATES_DIR, display_path, media_root, models_dir, project_dir
from .errors import AdapterError, RunnerError
from .loader import (
    discover_projects,
    discover_shots,
    load_pipeline,
    load_project,
    load_shot,
    parse_target,
)
from .models import PROJECT_ID_RE, SHOT_ID_RE
from .plan import parse_set_values, plan_shot
from .render import render_shot
from .schemas import generate_schemas
from .validate import validate

TEXT_SUFFIXES = {".yaml", ".yml", ".json", ".md", ".txt", ".sh", ".py", ".toml"}


def _require_shot(target: str | None) -> tuple[str, str]:
    project_id, shot_id = parse_target(target)
    if not project_id or not shot_id:
        raise RunnerError("target must be project/shot, for example demo_01/s010")
    return project_id, shot_id


def _replace_placeholders(root: Path, replacements: dict[str, str]) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        for key, value in replacements.items():
            text = text.replace(key, value)
        path.write_text(text, encoding="utf-8")


def cmd_new_project(args: argparse.Namespace) -> int:
    if not PROJECT_ID_RE.fullmatch(args.project_id):
        raise RunnerError(
            "project id must match ^[a-z][a-z0-9_]{2,31}$ "
            "(lowercase letters, digits, underscore; 3-32 chars)"
        )
    destination = PROJECTS_DIR / args.project_id
    if destination.exists():
        raise RunnerError(f"project already exists: {display_path(destination)}")
    template = TEMPLATES_DIR / "project"
    if not template.exists():
        raise RunnerError(f"project template is missing: {display_path(template)}")
    owner = args.owner or os.environ.get("USER") or getpass.getuser()
    title = (args.title or args.project_id.replace("_", " ").title()).replace('"', "'")
    shutil.copytree(template, destination)
    _replace_placeholders(
        destination,
        {
            "__PROJECT_ID__": args.project_id,
            "__PROJECT_TITLE__": title,
            "__OWNER__": owner.replace('"', "'"),
            "__SHOT_ID__": "s010",
            "__SHOT_TITLE__": "Opening shot",
        },
    )
    for name in ("assets", "deliverables", "state"):
        (destination / name).mkdir(exist_ok=True)
    print(f"created {display_path(destination)}")
    print(f"next: ./vp validate projects/{args.project_id}")
    return 0


def cmd_new_shot(args: argparse.Namespace) -> int:
    if not SHOT_ID_RE.fullmatch(args.shot_id):
        raise RunnerError(
            "shot id must match ^[a-z][a-z0-9_]{1,31}$ (for example s020)"
        )
    project = load_project(args.project_id)
    destination = project_dir(project.id) / "shots" / args.shot_id
    if destination.exists():
        raise RunnerError(f"shot already exists: {display_path(destination)}")
    template = TEMPLATES_DIR / "shot"
    if not template.exists():
        raise RunnerError(f"shot template is missing: {display_path(template)}")
    title = (args.title or f"Shot {args.shot_id}").replace('"', "'")
    shutil.copytree(template, destination)
    _replace_placeholders(
        destination,
        {
            "__PROJECT_ID__": project.id,
            "__SHOT_ID__": args.shot_id,
            "__SHOT_TITLE__": title,
        },
    )
    (project_dir(project.id) / "assets" / args.shot_id).mkdir(
        parents=True, exist_ok=True
    )
    print(f"created {display_path(destination)}")
    print(f"next: edit {display_path(destination / 'shot.yaml')} and run ./vp validate {project.id}/{args.shot_id}")
    return 0


def _print_plan(plan) -> None:
    print(f"Project: {plan.project.id} — {plan.project.title}")
    print(f"Shot:    {plan.shot.id} — {plan.shot.title}")
    print(f"Profile: {plan.profile}")
    print()
    for stage in plan.stages:
        flags = []
        if stage.selected:
            flags.append("selected")
        if not stage.enabled:
            flags.append("disabled")
        flag_text = f" [{', '.join(flags)}]" if flags else ""
        print(f"Stage {stage.id}{flag_text} ({stage.adapter}, {stage.action})")
        if stage.model_id:
            print(f"  model:    {stage.model_id}")
        if stage.output:
            print(f"  output:   {stage.output}")
            if stage.output_path:
                print(f"  resolved: {display_path(stage.output_path)}")
        if stage.workflow_file:
            print(f"  workflow: {stage.workflow_file}")
        if stage.input_paths:
            print("  inputs:")
            for path in stage.input_paths:
                print(f"    - {display_path(path)}")
        if stage.params:
            print("  params:")
            for key, value in stage.params.items():
                print(f"    {key}: {value}")
        for warning in stage.warnings:
            print(f"  warning: {warning}")
        for error in stage.errors:
            print(f"  error:   {error}")
        print()
    if plan.warnings:
        print("Warnings:")
        for warning in plan.warnings:
            print(f"  - {warning}")
    if plan.errors:
        print("Errors:")
        for error in plan.errors:
            print(f"  - {error}")


def cmd_plan(args: argparse.Namespace) -> int:
    project_id, shot_id = _require_shot(args.target)
    plan = plan_shot(
        project_id,
        shot_id,
        stage_ids=[args.stage] if args.stage else None,
        profile_override=args.profile,
        seed_override=args.seed,
        set_values=parse_set_values(args.set),
        check_models=args.check_models,
    )
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
    else:
        _print_plan(plan)
    return 1 if plan.errors else 0


def cmd_render(args: argparse.Namespace) -> int:
    project_id, shot_id = _require_shot(args.target)
    set_values = parse_set_values(args.set)
    if args.dry_run:
        plan = plan_shot(
            project_id,
            shot_id,
            stage_ids=[args.stage] if args.stage else None,
            profile_override=args.profile,
            seed_override=args.seed,
            set_values=set_values,
            check_models=args.check_models,
        )
        print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
        return 1 if plan.errors else 0
    plan, manifests = render_shot(
        project_id,
        shot_id,
        stage_id=args.stage,
        all_stages=args.all,
        profile=args.profile,
        seed=args.seed,
        set_values=set_values,
        yes=args.yes,
        check_models=args.check_models,
    )
    print(f"rendered {plan.project.id}/{plan.shot.id}")
    for manifest in manifests:
        print(f"manifest: {display_path(manifest)}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate(args.target, no_git=args.no_git)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": report.ok,
                    "projects": report.checked_projects,
                    "shots": report.checked_shots,
                    "errors": report.errors,
                    "warnings": report.warnings,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(
            f"checked {report.checked_projects} project(s), "
            f"{report.checked_shots} shot(s)"
        )
        if report.errors:
            print("\nErrors:")
            for error in report.errors:
                print(f"  - {error}")
        if report.warnings:
            print("\nWarnings:")
            for warning in report.warnings:
                print(f"  - {warning}")
        if report.ok:
            print("\nOK")
    return 0 if report.ok else 1


def cmd_schemas(args: argparse.Namespace) -> int:
    paths = generate_schemas()
    for path in paths:
        print(f"wrote {display_path(path)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    projects = discover_projects()
    if not projects:
        print("no projects found")
        return 0
    for project_id in projects:
        try:
            project = load_project(project_id)
            pipeline = load_pipeline(project)
        except RunnerError as exc:
            print(f"{project_id}: ERROR: {exc}")
            continue
        shots = discover_shots(project_id)
        print(f"{project.id}  {project.title}  [{project.status}]  {len(shots)} shot(s)")
        for shot_id in shots:
            try:
                shot = load_shot(project_id, shot_id)
                print(f"  {shot.id}  {shot.title}  [{shot.status}]")
            except RunnerError as exc:
                print(f"  {shot_id}  ERROR: {exc}")
        print(f"  stages: {', '.join(stage.id for stage in pipeline.stages)}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    problems = 0

    def line(status: str, message: str) -> None:
        nonlocal problems
        if status == "fail":
            problems += 1
        print(f"[{status}] {message}")

    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 10):
        line("ok", f"Python {platform.python_version()}")
    else:
        line("fail", f"Python {platform.python_version()} (need 3.10+)")

    try:
        import yaml  # noqa: F401

        line("ok", f"PyYAML {yaml.__version__}")
    except Exception as exc:  # pragma: no cover - environment check
        line("fail", f"PyYAML is not available: {exc}")

    try:
        import pydantic  # noqa: F401

        line("ok", f"pydantic {pydantic.__version__}")
    except Exception as exc:  # pragma: no cover - environment check
        line("fail", f"pydantic is not available: {exc}")

    for tool in ("git", "ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        line("ok" if path else "warn", f"{tool}: {path or 'not found'}")

    root = media_root()
    line(
        "ok" if root else "warn",
        f"MEDIA_ROOT: {root if root else 'not set (using per-project assets/)'}",
    )
    model_root = models_dir()
    line(
        "ok" if model_root else "warn",
        f"MODELS_DIR: {model_root if model_root else 'not set'}",
    )

    if not args.no_comfyui:
        endpoint = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
        try:
            ComfyUIAdapter().health()
            line("ok", f"ComfyUI reachable at {endpoint}")
        except AdapterError as exc:
            line("warn", f"ComfyUI not reachable at {endpoint}: {exc}")

    if subprocess.run(
        ["git", "-C", str(PROJECTS_DIR.parent), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        check=False,
    ).returncode == 0:
        line("ok", "git repository detected")
    else:
        line("warn", "not a git repository")

    return 1 if problems else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vp",
        description="Video pipelines control-plane runner",
    )
    parser.add_argument("--version", action="version", version=f"vp {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="validate projects and shots")
    validate_parser.add_argument("target", nargs="?", help="project or project/shot")
    validate_parser.add_argument("--json", action="store_true", help="machine-readable output")
    validate_parser.add_argument("--no-git", action="store_true", help="skip git media/secret checks")
    validate_parser.set_defaults(func=cmd_validate)

    plan_parser = sub.add_parser("plan", help="resolve a shot into render jobs")
    plan_parser.add_argument("target", help="project/shot")
    plan_parser.add_argument("--stage", help="only this stage")
    plan_parser.add_argument("--profile", help="override the render profile")
    plan_parser.add_argument("--seed", type=int, help="override the seed")
    plan_parser.add_argument("--set", action="append", metavar="KEY=VALUE", help="override a parameter")
    plan_parser.add_argument("--json", action="store_true", help="machine-readable output")
    plan_parser.add_argument("--check-models", action="store_true", help="check local model paths")
    plan_parser.set_defaults(func=cmd_plan)

    render_parser = sub.add_parser("render", help="render one stage or all stages")
    render_parser.add_argument("target", help="project/shot")
    render_group = render_parser.add_mutually_exclusive_group()
    render_group.add_argument("--stage", help="stage to render")
    render_group.add_argument("--all", action="store_true", help="render all enabled stages")
    render_parser.add_argument("--profile", help="override the render profile")
    render_parser.add_argument("--seed", type=int, help="override the seed")
    render_parser.add_argument("--set", action="append", metavar="KEY=VALUE", help="override a parameter")
    render_parser.add_argument("--yes", action="store_true", help="confirm final/all renders")
    render_parser.add_argument("--dry-run", action="store_true", help="print the resolved plan only")
    render_parser.add_argument("--check-models", action="store_true", help="check local model paths")
    render_parser.set_defaults(func=cmd_render)

    new_project_parser = sub.add_parser("new-project", help="scaffold a project from the template")
    new_project_parser.add_argument("project_id")
    new_project_parser.add_argument("--title")
    new_project_parser.add_argument("--owner")
    new_project_parser.set_defaults(func=cmd_new_project)

    new_shot_parser = sub.add_parser("new-shot", help="scaffold a shot from the template")
    new_shot_parser.add_argument("project_id")
    new_shot_parser.add_argument("shot_id")
    new_shot_parser.add_argument("--title")
    new_shot_parser.set_defaults(func=cmd_new_shot)

    schemas_parser = sub.add_parser("schemas", help="regenerate JSON schemas")
    schemas_parser.set_defaults(func=cmd_schemas)

    list_parser = sub.add_parser("list", help="list projects and shots")
    list_parser.set_defaults(func=cmd_list)

    doctor_parser = sub.add_parser("doctor", help="check the local environment")
    doctor_parser.add_argument("--no-comfyui", action="store_true", help="skip the ComfyUI probe")
    doctor_parser.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if os.environ.get("VP_DEBUG"):
            raise
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
