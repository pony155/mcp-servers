"""Stable domain errors exposed by Aseprite MCP tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class AsepriteMCPError(RuntimeError):
    """An expected, actionable failure in an Aseprite operation."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = dict(details or {})
        super().__init__(f"{code}: {message}")


def require(condition: bool, code: str, message: str) -> None:
    """Raise a stable domain error when a precondition is not satisfied."""

    if not condition:
        raise AsepriteMCPError(code, message)
