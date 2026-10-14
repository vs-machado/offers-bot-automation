"""Carry source timestamps through async processing without changing callbacks."""

from contextvars import ContextVar

promotion_context: ContextVar[dict[str, str | None]] = ContextVar(
    "promotion_context", default={}
)

source_timestamp: ContextVar[float | None] = ContextVar(
    "source_timestamp", default=None
)
