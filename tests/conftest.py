"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sentinel.contracts import TrackObservation
from sentinel.events.state import Zone


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def square_zone() -> Zone:
    return Zone(zone_id="z1", polygon=[(0, 0), (10, 0), (10, 10), (0, 10)])


def make_obs(
    track_id: int,
    ground_px: tuple[float, float],
    t: datetime,
    class_name: str = "person",
    confidence: float = 0.9,
    ground_m: tuple[float, float] | None = None,
    velocity_mps: tuple[float, float] | None = None,
) -> TrackObservation:
    from sentinel.contracts import BoundingBox

    x, y = ground_px
    return TrackObservation(
        camera_id="cam",
        track_id=track_id,
        timestamp=t,
        class_name=class_name,
        confidence=confidence,
        box=BoundingBox(x - 5, y - 20, x + 5, y),
        centroid_px=(x, y - 10),
        ground_point_px=ground_px,
        ground_point_m=ground_m,
        velocity_mps=velocity_mps,
    )


def advance(t: datetime, seconds: float) -> datetime:
    return t + timedelta(seconds=seconds)
