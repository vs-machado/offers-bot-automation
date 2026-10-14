"""Carry source timestamps through async processing without changing callbacks."""

from contextvars import ContextVar

source_timestamp: ContextVar[float | None] = ContextVar(
    "source_timestamp", default=None
)
