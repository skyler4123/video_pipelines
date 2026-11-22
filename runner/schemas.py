from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from .config import SCHEMAS_DIR
from .models import (
    ModelSpec,
    Pipeline,
    Project,
    Shot,
    ToolSpec,
    WorkflowMap,
)


def generate_schemas(output_dir: Path = SCHEMAS_DIR) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    schemas = {
        "project.schema.json": Project.model_json_schema(),
        "pipeline.schema.json": Pipeline.model_json_schema(),
        "shot.schema.json": Shot.model_json_schema(),
        "workflow-map.schema.json": WorkflowMap.model_json_schema(),
        "models.schema.json": TypeAdapter(dict[str, ModelSpec]).json_schema(),
        "tools.schema.json": TypeAdapter(dict[str, ToolSpec]).json_schema(),
    }
    paths: list[Path] = []
    for name, schema in schemas.items():
        schema.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
        path = output_dir / name
        path.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths
