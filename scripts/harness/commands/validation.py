"""Shared validation helpers for Blender commands."""

from __future__ import annotations

from ..errors import HarnessError


def require_name(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HarnessError("INVALID_ARGUMENT", "name must be a non-empty string")
    return value.strip()


def vector3(value, field: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise HarnessError("INVALID_ARGUMENT", f"{field} must contain three numbers")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise HarnessError("INVALID_ARGUMENT", f"{field} must contain three numbers")
    return [float(item) for item in value]


def closed_arguments(*, required=(), optional=()):
    allowed = set(required) | set(optional)
    required_fields = set(required)

    def validate(arguments: dict) -> None:
        unknown = sorted(set(arguments) - allowed)
        missing = sorted(required_fields - set(arguments))
        if unknown:
            raise HarnessError("INVALID_ARGUMENT", f"unknown argument fields: {unknown}")
        if missing:
            raise HarnessError("INVALID_ARGUMENT", f"missing argument fields: {missing}")

    return validate
