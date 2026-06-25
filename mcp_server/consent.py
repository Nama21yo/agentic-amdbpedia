"""Consent hooks for future destructive MCP tools."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


class ConsentRequiredError(PermissionError):
    """Raised when a consent-gated operation is attempted without approval."""


def require_consent(approved: bool = False) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Block a tool until its caller has explicit user approval."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if not approved:
                raise ConsentRequiredError("Explicit user consent is required for this action")
            return func(*args, **kwargs)

        return wrapper

    return decorator
