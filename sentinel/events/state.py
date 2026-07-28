"""Shared state helpers for the event engine (zones, dwell, cooldown, debounce)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

Vec = tuple[float, float]


@dataclass(frozen=True)
class Zone:
    """A named ground-plane polygon in image pixel coordinates."""

    zone_id: str
    polygon: list[Vec]
    camera_id: str | None = None


class ZonePhase(str, Enum):
    OUTSIDE = "outside"
    PENDING_ENTRY = "pending_entry"
    INSIDE = "inside"
    PENDING_EXIT = "pending_exit"


@dataclass
class ZoneTrackState:
    phase: ZonePhase = ZonePhase.OUTSIDE
    pending_since: datetime | None = None
    inside_since: datetime | None = None
    last_seen: datetime | None = None


class Cooldown:
    """Suppresses repeated emissions for the same dedup key within a window."""

    def __init__(self) -> None:
        self._last: dict[tuple, datetime] = {}

    def ready(self, key: tuple, now: datetime, cooldown_seconds: float) -> bool:
        last = self._last.get(key)
        if last is None:
            return True
        return (now - last).total_seconds() >= cooldown_seconds

    def mark(self, key: tuple, now: datetime) -> None:
        self._last[key] = now
