"""Closed registry for Blender Harness commands."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from .errors import HarnessError


@dataclass(frozen=True)
class CommandDefinition:
    handler: Callable[[dict], dict]
    validate: Callable[[dict], None] | None = None
    risk: str = "standard"


class CommandRegistry:
    def __init__(self):
        self._commands: dict[str, CommandDefinition] = {}

    def register(self, name: str, handler, *, validate=None, risk: str = "standard") -> None:
        if name in self._commands:
            raise HarnessError("DUPLICATE_COMMAND", f"command already registered: {name}")
        if risk not in {"read", "standard", "gated"}:
            raise HarnessError("INVALID_COMMAND_DEFINITION", f"unknown risk: {risk}")
        self._commands[name] = CommandDefinition(handler=handler, validate=validate, risk=risk)

    def dispatch(self, name: str, arguments: dict) -> dict:
        definition = self._commands.get(name)
        if definition is None:
            raise HarnessError("UNKNOWN_COMMAND", f"unknown command: {name}")
        if not isinstance(arguments, dict):
            raise HarnessError("INVALID_ARGUMENT", "command arguments must be an object")
        if definition.validate is not None:
            definition.validate(arguments)
        result = definition.handler(arguments)
        if result is None:
            return {}
        if not isinstance(result, dict):
            raise HarnessError("INVALID_COMMAND_RESULT", f"command {name} returned a non-object")
        return result

    def capabilities(self) -> list[dict]:
        return [
            {"command": name, "risk": definition.risk}
            for name, definition in sorted(self._commands.items())
        ]

