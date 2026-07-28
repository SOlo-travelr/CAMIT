"""Unit tests for deterministic geometry primitives."""

from __future__ import annotations

from sentinel.events.geometry import (
    closest_approach,
    crossing_direction,
    estimate_velocity,
    point_in_polygon,
    segment_crosses_line,
)


def test_point_in_polygon_inside_and_outside():
    poly = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5, 5), poly) is True
    assert point_in_polygon((15, 5), poly) is False
    assert point_in_polygon((0, 0), poly) is True  # boundary counts


def test_segment_crossing():
    assert segment_crosses_line((0, 0), (0, 10), (-5, 5), (5, 5)) is True
    assert segment_crosses_line((0, 0), (0, 4), (-5, 5), (5, 5)) is False


def test_crossing_direction_sign_flips():
    d1 = crossing_direction((-1, 0), (1, 0), (0, -5), (0, 5))
    d2 = crossing_direction((1, 0), (-1, 0), (0, -5), (0, 5))
    assert d1 == -d2
    assert d1 != 0


def test_estimate_velocity_constant():
    positions = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
    ts = [0.0, 1.0, 2.0, 3.0]
    vx, vy = estimate_velocity(positions, ts, smooth_window=1)
    assert abs(vx - 1.0) < 1e-6
    assert abs(vy) < 1e-6


def test_parallel_trajectories_do_not_trigger_collision():
    # Two objects moving parallel, 5 m apart, never converge.
    ca = closest_approach((0, 0), (1, 0), (0, 5), (1, 0), horizon_s=3)
    assert ca.min_distance >= 4.9
    assert ca.current_distance == 5.0


def test_head_on_near_miss_predicts_small_distance():
    # Person +x at 1 m/s, vehicle -x at 2 m/s, 0.6 m lateral offset, closing.
    ca = closest_approach((5, 0), (1, 0), (7, 0.6), (-2, 0), horizon_s=3)
    assert ca.min_distance < 1.0
    assert 0 <= ca.time_to_closest_s <= 3
