from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,31}$")
SHOT_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
STAGE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectDefaults(StrictModel):
    profile: str = "animatic"
    pipeline: str = "pipeline.yaml"


class Variant(StrictModel):
    aspect: str
    width: int
    height: int


class Project(StrictModel):
    schema_version: int = Field(1, alias="schema")
    id: str
    title: str
    status: Literal["active", "paused", "archived"] = "active"
    owner: str | None = None
    description: str | None = None
    defaults: ProjectDefaults = Field(default_factory=ProjectDefaults)
    variants: dict[str, Variant] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not PROJECT_ID_RE.fullmatch(value):
            raise ValueError(
                "project id must match ^[a-z][a-z0-9_]{2,31}$ "
                "(lowercase letters, digits, underscore; 3-32 chars)"
            )
        return value

    @field_validator("defaults")
    @classmethod
    def validate_profile(cls, value: ProjectDefaults) -> ProjectDefaults:
        if not value.profile:
            raise ValueError("default profile cannot be empty")
        return value


class Stage(StrictModel):
    id: str
    adapter: Literal["comfyui", "diffusers", "ffmpeg", "hosted_api", "mock"]
    action: Literal["generate", "qc", "assemble", "encode"] = "generate"
    workflow: str | None = None
    map: str | None = None
    model: str | None = None
    enabled: bool = True
    depends_on: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not STAGE_ID_RE.fullmatch(value):
            raise ValueError(
                "stage id must match ^[a-z][a-z0-9_]{1,31}$"
            )
        return value


class Pipeline(StrictModel):
    schema_version: int = Field(1, alias="schema")
    stages: list[Stage]

    @model_validator(mode="after")
    def validate_stages(self) -> Pipeline:
        ids = [stage.id for stage in self.stages]
        if len(ids) != len(set(ids)):
            raise ValueError("stage ids must be unique")
        seen: set[str] = set()
        for stage in self.stages:
            for dependency in stage.depends_on:
                if dependency not in ids:
                    raise ValueError(
                        f"stage {stage.id!r} depends on unknown stage {dependency!r}"
                    )
                if dependency not in seen:
                    raise ValueError(
                        f"stage {stage.id!r} depends on {dependency!r}, "
                        "which is not earlier in the pipeline"
                    )
            seen.add(stage.id)
        return self


class RenderDefaults(StrictModel):
    profile: str = "animatic"
    seed: int | None = None


class Prompt(StrictModel):
    positive: str
    negative: str = ""


class StageOverride(StrictModel):
    model: str | None = None
    profile: str | None = None
    seed: int | None = None
    output: str | None = None
    workflow: str | None = None
    map: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class QC(StrictModel):
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    frames: int | None = None
    duration: float | None = None


class Approval(StrictModel):
    run_id: str
    approved_by: str
    approved_at: str
    sha256: str | None = None


class Shot(StrictModel):
    schema_version: int = Field(1, alias="schema")
    id: str
    title: str
    status: Literal[
        "draft", "in_review", "approved", "final", "archived"
    ] = "draft"
    refs: dict[str, str] = Field(default_factory=dict)
    render: RenderDefaults = Field(default_factory=RenderDefaults)
    prompt: Prompt
    stages: dict[str, StageOverride] = Field(default_factory=dict)
    qc: QC | None = None
    approvals: list[Approval] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not SHOT_ID_RE.fullmatch(value):
            raise ValueError(
                "shot id must match ^[a-z][a-z0-9_]{1,31}$ "
                "(for example s010)"
            )
        return value


class ParamMapping(StrictModel):
    node_title: str | None = None
    node_id: str | None = None
    input: str
    required: bool = True

    @model_validator(mode="after")
    def validate_target(self) -> ParamMapping:
        if bool(self.node_title) == bool(self.node_id):
            raise ValueError("exactly one of node_title or node_id must be set")
        return self


class WorkflowMap(StrictModel):
    schema_version: int = Field(1, alias="schema")
    params: dict[str, ParamMapping] = Field(default_factory=dict)


class ModelSpec(StrictModel):
    kind: Literal["image", "video", "audio", "llm", "other"]
    source: Literal["local", "hosted"] = "local"
    path: str | None = None
    endpoint: str | None = None
    sha256: str | None = None
    license: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    presets: dict[str, dict[str, Any]] = Field(default_factory=dict)
    notes: str | None = None


class ToolSpec(StrictModel):
    kind: str
    endpoint: str | None = None
    image: str | None = None
    version: str | None = None
    custom_nodes_lock: str | None = None
    notes: str | None = None


class ProfilePreset(StrictModel):
    description: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
