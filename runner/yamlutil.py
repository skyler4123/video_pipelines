from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import yaml

from .errors import RunnerError


def load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise RunnerError(f"missing file: {path}") from exc
    except yaml.YAMLError as exc:
        raise RunnerError(f"invalid YAML in {path}: {exc}") from exc


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise RunnerError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(f"invalid JSON in {path}: {exc}") from exc


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(data), encoding="utf-8")


def walk_strings(data: Any, prefix: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from walk_strings(value, child)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            child = f"{prefix}[{index}]"
            yield from walk_strings(value, child)
    elif isinstance(data, str):
        yield prefix, data
