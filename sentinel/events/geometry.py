"""Deterministic geometry primitives for the event engine.

Pure functions with no I/O. These are the calculations the LLM is explicitly
forbidden from performing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, Point, Polygon

Vec = tuple[float, float]


# ---------------------------------------------------------------------------
# Polygons / zones
# ---------------------------------------------------------------------------


def point_in_polygon(point: Vec, polygon: list[Vec]) -> bool:
    """Return True if ``point`` lies inside (or on the boundary of) ``polygon``."""
    if len(polygon) < 3:
        return False
    poly = Polygon(polygon)
    p = Point(point)
    return bool(poly.covers(p))


def segment_crosses_line(p0: Vec, p1: Vec, a: Vec, b: Vec) -> bool:
    """Return True if the segment ``p0->p1`` intersects the line segment ``a->b``."""
    return bool(LineString([p0, p1]).intersects(LineString([a, b])))


def crossing_direction(p0: Vec, p1: Vec, a: Vec, b: Vec) -> int:
    """Sign of the crossing of ``p0->p1`` relative to directed line ``a->b``.

    Returns +1 / -1 for the two crossing directions, 0 if it does not cross.
    """
    if not segment_crosses_line(p0, p1, a, b):
        return 0
    line = np.array(b, dtype=float) - np.array(a, dtype=float)

    def side(pt: Vec) -> float:
        rel = np.array(pt, dtype=float) - np.array(a, dtype=float)
        return float(line[0] * rel[1] - line[1] * rel[0])

    s0, s1 = side(p0), side(p1)
    if s0 <= 0 < s1:
        return 1
    if s0 >= 0 > s1:
        return -1
    return 0


# ---------------------------------------------------------------------------
# Trajectory smoothing & velocity
# ---------------------------------------------------------------------------


def moving_average(points: list[Vec], window: int = 3) -> list[Vec]:
    """Smooth a sequence of 2D points with a centered moving average."""
    if window <= 1 or len(points) < window:
        return list(points)
    arr = np.asarray(points, dtype=float)
    kernel = np.ones(window) / window
    xs = np.convolve(arr[:, 0], kernel, mode="same")
    ys = np.convolve(arr[:, 1], kernel, mode="same")
    return list(zip(xs.tolist(), ys.tolist(), strict=False))


def estimate_velocity(
    positions: list[Vec], timestamps: list[float], smooth_window: int = 3
) -> Vec:
    """Estimate velocity (units/second) from recent positions via least squares."""
    if len(positions) < 2:
        return (0.0, 0.0)
    pts = moving_average(positions, smooth_window) if len(positions) >= smooth_window else positions
    t = np.asarray(timestamps, dtype=float)
    t = t - t[0]
    arr = np.asarray(pts, dtype=float)
    if np.allclose(t, t[0]):
        return (0.0, 0.0)
    # Linear fit per axis; slope is velocity.
    A = np.vstack([t, np.ones_like(t)]).T
    vx, _ = np.linalg.lstsq(A, arr[:, 0], rcond=None)[0]
    vy, _ = np.linalg.lstsq(A, arr[:, 1], rcond=None)[0]
    return (float(vx), float(vy))


# ---------------------------------------------------------------------------
# Closest approach (constant-velocity model)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClosestApproach:
    time_to_closest_s: float
    min_distance: float
    current_distance: float
    relative_speed: float


def closest_approach(
    p_a: Vec, v_a: Vec, p_b: Vec, v_b: Vec, horizon_s: float, eps: float = 1e-9
) -> ClosestApproach:
    """Constant-velocity time-to-closest-approach and predicted minimum distance.

    r = p_a - p_b ; u = v_a - v_b
    t* = clip(-(r . u) / |u|^2, 0, H)
    d_min = |r + t* u|
    """
    r = np.array(p_a, dtype=float) - np.array(p_b, dtype=float)
    u = np.array(v_a, dtype=float) - np.array(v_b, dtype=float)
    current = float(np.linalg.norm(r))
    rel_speed = float(np.linalg.norm(u))
    denom = float(u.dot(u)) + eps
    t_star = float(np.clip(-(r.dot(u)) / denom, 0.0, horizon_s))
    d_min = float(np.linalg.norm(r + t_star * u))
    return ClosestApproach(
        time_to_closest_s=t_star,
        min_distance=d_min,
        current_distance=current,
        relative_speed=rel_speed,
    )


def euclidean(a: Vec, b: Vec) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))
