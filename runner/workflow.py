from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .errors import RunnerError
from .models import ParamMapping, WorkflowMap
from .yamlutil import load_json


def load_workflow(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise RunnerError(f"workflow {path} must be a JSON object")
    return data


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def validate_api_workflow(workflow: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not workflow:
        return ["workflow must contain at least one node"]
    for node_id, node in workflow.items():
        if not isinstance(node_id, str):
            errors.append(f"node id {node_id!r} must be a string")
        if not isinstance(node, dict):
            errors.append(f"node {node_id!r} must be an object")
            continue
        if not isinstance(node.get("class_type"), str) or not node["class_type"]:
            errors.append(f"node {node_id!r} is missing class_type")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            errors.append(f"node {node_id!r} is missing an inputs object")
            continue
        for input_name, value in inputs.items():
            if not _is_link(value):
                continue
            target = value[0]
            if target not in workflow:
                errors.append(
                    f"node {node_id!r} input {input_name!r} links to "
                    f"missing node {target!r}"
                )
            if value[1] < 0:
                errors.append(
                    f"node {node_id!r} input {input_name!r} has a negative output index"
                )
    return errors


def index_nodes(
    workflow: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_title: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        by_id[str(node_id)] = node
        meta = node.get("_meta")
        title = meta.get("title") if isinstance(meta, dict) else None
        if isinstance(title, str) and title:
            if title in by_title:
                errors.append(f"duplicate node title {title!r}")
            else:
                by_title[title] = node
    return by_id, by_title, errors


def _resolve_node(
    mapping: ParamMapping,
    by_id: dict[str, dict[str, Any]],
    by_title: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    if mapping.node_title:
        node = by_title.get(mapping.node_title)
        if node is None:
            return None, f"node title {mapping.node_title!r} was not found"
        return node, None
    node = by_id.get(str(mapping.node_id))
    if node is None:
        return None, f"node id {mapping.node_id!r} was not found"
    return node, None


def apply_params(
    workflow: dict[str, Any],
    mapping: WorkflowMap,
    params: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str]]:
    """Return a copy of the workflow with mapped parameters applied.

    Returns (workflow, applied, warnings, errors). The caller decides whether
    errors are fatal.
    """
    result = copy.deepcopy(workflow)
    applied: dict[str, Any] = {}
    warnings: list[str] = []
    errors: list[str] = []

    by_id, by_title, index_errors = index_nodes(result)
    errors.extend(index_errors)

    for key, spec in mapping.params.items():
        if key not in params:
            if spec.required:
                errors.append(f"missing required parameter {key!r}")
            continue
        node, error = _resolve_node(spec, by_id, by_title)
        if node is None:
            errors.append(f"parameter {key!r}: {error}")
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            errors.append(f"parameter {key!r}: target node has no inputs object")
            continue
        if spec.input not in inputs:
            errors.append(
                f"parameter {key!r}: node has no input named {spec.input!r}"
            )
            continue
        inputs[spec.input] = params[key]
        applied[key] = params[key]

    for key in params:
        if key not in mapping.params:
            warnings.append(f"parameter {key!r} is not mapped and will be ignored")

    return result, applied, warnings, errors


def validate_mapping(workflow: dict[str, Any], mapping: WorkflowMap) -> list[str]:
    errors: list[str] = []
    by_id, by_title, index_errors = index_nodes(workflow)
    errors.extend(index_errors)
    for key, spec in mapping.params.items():
        node, error = _resolve_node(spec, by_id, by_title)
        if node is None:
            errors.append(f"parameter {key!r}: {error}")
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or spec.input not in inputs:
            errors.append(
                f"parameter {key!r}: node has no input named {spec.input!r}"
            )
    return errors


def topology_hash(workflow: dict[str, Any]) -> str:
    """Hash the graph shape, ignoring scalar parameter values."""
    topology: dict[str, Any] = {}
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        meta = node.get("_meta")
        title = meta.get("title") if isinstance(meta, dict) else None
        inputs = node.get("inputs")
        links = {
            name: value
            for name, value in (inputs or {}).items()
            if _is_link(value)
        }
        topology[str(node_id)] = {
            "class_type": node.get("class_type"),
            "title": title,
            "links": links,
        }
    canonical = json.dumps(topology, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
