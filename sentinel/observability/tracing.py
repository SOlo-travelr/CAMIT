"""Tracing shim. Real OpenTelemetry wiring is optional and added at deploy time."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def span(name: str) -> Iterator[None]:
    """No-op span context manager used until OpenTelemetry is configured."""
    yield
