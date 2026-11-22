from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..models import ModelSpec


@dataclass
class Job:
    run_id: str
    project_id: str
    shot_id: str
    stage_id: str
    adapter: str
    action: str
    profile: str
    output_logical: str | None
    output_dir: Path | None
    input_paths: list[Path]
    workflow: dict[str, Any] | None
    workflow_path: Path | None
    params: dict[str, Any]
    model_id: str | None
    model: ModelSpec | None
    qc: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterResult:
    status: str = "succeeded"
    outputs: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class BaseAdapter:
    name = "base"

    def run(self, job: Job) -> AdapterResult:
        raise NotImplementedError
