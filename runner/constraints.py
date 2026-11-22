from __future__ import annotations

import re
from typing import Any

from .models import ModelSpec


def leaf_values(params: dict[str, Any], leaf: str) -> list[tuple[str, Any]]:
    values: list[tuple[str, Any]] = []
    for key, value in params.items():
        if key == leaf or key.endswith(f".{leaf}"):
            values.append((key, value))
    return values


def _as_number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _check_multiple(
    params: dict[str, Any], leaf: str, multiple: Any, errors: list[str]
) -> None:
    number = _as_number(multiple)
    if number is None or int(number) <= 0:
        errors.append(f"constraint {leaf}_multiple must be a positive integer")
        return
    for key, value in leaf_values(params, leaf):
        candidate = _as_number(value)
        if candidate is None:
            errors.append(f"{key} must be a number")
        elif int(candidate) % int(number) != 0:
            errors.append(f"{key}={candidate} must be a multiple of {int(number)}")


def _check_range(
    params: dict[str, Any],
    leaf: str,
    constraint: str,
    limit: Any,
    errors: list[str],
) -> None:
    boundary = _as_number(limit)
    if boundary is None:
        errors.append(f"constraint {constraint} must be a number")
        return
    for key, value in leaf_values(params, leaf):
        candidate = _as_number(value)
        if candidate is None:
            errors.append(f"{key} must be a number")
        elif constraint.startswith("min") and candidate < boundary:
            errors.append(f"{key}={candidate} must be >= {boundary}")
        elif constraint.startswith("max") and candidate > boundary:
            errors.append(f"{key}={candidate} must be <= {boundary}")


def _check_frames(params: dict[str, Any], expression: Any, errors: list[str]) -> None:
    if not isinstance(expression, str):
        errors.append("constraint frames must be a string such as '4n+1'")
        return
    match = re.fullmatch(r"(\d+)n\+(\d+)", expression.strip())
    if not match:
        errors.append(
            f"unsupported frames constraint {expression!r}; expected '4n+1'"
        )
        return
    step = int(match.group(1))
    offset = int(match.group(2))
    if step <= 0:
        errors.append("frames constraint step must be positive")
        return
    for key, value in leaf_values(params, "frames"):
        candidate = _as_number(value)
        if candidate is None:
            errors.append(f"{key} must be a number")
            continue
        if int(candidate) != candidate:
            errors.append(f"{key} must be an integer")
        elif (int(candidate) - offset) % step != 0:
            errors.append(
                f"{key}={candidate} does not satisfy {expression} "
                f"(valid values: {offset}, {offset + step}, {offset + 2 * step}, ...)"
            )


def check_constraints(
    model: ModelSpec, params: dict[str, Any]
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    constraints = model.constraints or {}
    for key, value in constraints.items():
        if key == "frames":
            _check_frames(params, value, errors)
        elif key == "width_multiple":
            _check_multiple(params, "width", value, errors)
        elif key == "height_multiple":
            _check_multiple(params, "height", value, errors)
        elif key in {"min_frames", "max_frames"}:
            _check_range(params, "frames", key, value, errors)
        elif key in {"min_width", "max_width"}:
            _check_range(params, "width", key, value, errors)
        elif key in {"min_height", "max_height"}:
            _check_range(params, "height", key, value, errors)
        elif key in {"min_fps", "max_fps"}:
            _check_range(params, "fps", key, value, errors)
        else:
            warnings.append(f"unknown model constraint {key!r} is not checked")
    return errors, warnings
