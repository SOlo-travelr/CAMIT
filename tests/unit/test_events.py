"""Unit tests for event rules: zone debounce, dwell timer, cooldown, collision."""

from __future__ import annotations

from sentinel.events.collision_risk import CollisionRiskRule
from sentinel.events.loitering import LoiteringRule
from sentinel.events.restricted_zone import RestrictedZoneRule
from sentinel.events.state import Cooldown
from tests.conftest import advance, make_obs


def test_restricted_zone_fires_on_entry(base_time, square_zone):
    rule = RestrictedZoneRule(
        "p1", square_zone, "person", minimum_duration_ms=0,
        cooldown_seconds=30, severity="medium", confidence_threshold=0.4,
        cooldown=Cooldown(),
    )
    # Outside then inside -> one event.
    assert rule.update([make_obs(1, (20, 20), base_time)], base_time) == []
    out = rule.update([make_obs(1, (5, 5), advance(base_time, 0.1))], advance(base_time, 0.1))
    assert len(out) == 1
    assert out[0].event_type == "restricted_zone"


def test_boundary_jitter_does_not_repeat(base_time, square_zone):
    rule = RestrictedZoneRule(
        "p1", square_zone, "person", minimum_duration_ms=0,
        cooldown_seconds=30, severity="medium", confidence_threshold=0.4,
        cooldown=Cooldown(),
    )
    t = base_time
    fired = 0
    # Flip in/out repeatedly; cooldown must suppress repeats.
    for i in range(10):
        t = advance(base_time, i * 0.1)
        inside = (5, 5) if i % 2 == 0 else (20, 20)
        fired += len(rule.update([make_obs(1, inside, t)], t))
    assert fired == 1


def test_loitering_timer(base_time, square_zone):
    rule = LoiteringRule(
        "l1", square_zone, "person", minimum_seconds=5.0,
        max_tracking_gap_seconds=1.5, cooldown_seconds=30,
        severity="medium", confidence_threshold=0.4, cooldown=Cooldown(),
    )
    out = []
    for i in range(70):  # 7 seconds at 10 Hz
        t = advance(base_time, i * 0.1)
        out += rule.update([make_obs(1, (5, 5), t)], t)
    assert len(out) == 1
    assert out[0].evidence["dwell_seconds"] >= 5.0


def test_loitering_resets_on_exit(base_time, square_zone):
    rule = LoiteringRule(
        "l1", square_zone, "person", minimum_seconds=5.0,
        max_tracking_gap_seconds=1.5, cooldown_seconds=30,
        severity="medium", confidence_threshold=0.4, cooldown=Cooldown(),
    )
    out = []
    for i in range(30):  # 3s inside
        t = advance(base_time, i * 0.1)
        out += rule.update([make_obs(1, (5, 5), t)], t)
    # exit
    out += rule.update([make_obs(1, (20, 20), advance(base_time, 3.1))], advance(base_time, 3.1))
    for i in range(30):  # 3s inside again -> under 5s, no fire
        t = advance(base_time, 3.2 + i * 0.1)
        out += rule.update([make_obs(1, (5, 5), t)], t)
    assert out == []


def test_collision_requires_history_and_motion(base_time):
    rule = CollisionRiskRule(
        "c1", "person", "forklift", horizon_seconds=3.0, threshold_meters=1.0,
        minimum_vehicle_speed_mps=0.5, min_track_history=3, cooldown_seconds=30,
        severity="high", confidence_threshold=0.4, cooldown=Cooldown(),
    )
    out = []
    for i in range(6):
        t = advance(base_time, i * 0.1)
        person = make_obs(1, (100, 100), t, "person", ground_m=(5 + i * 0.1, 5.0), velocity_mps=(1.0, 0.0))
        veh = make_obs(2, (200, 100), t, "forklift", ground_m=(10 - i * 0.2, 5.6), velocity_mps=(-2.0, 0.0))
        out += rule.update([person, veh], t)
    assert any(c.event_type == "collision_risk" for c in out)


def test_collision_not_triggered_when_parallel(base_time):
    rule = CollisionRiskRule(
        "c1", "person", "forklift", horizon_seconds=3.0, threshold_meters=1.0,
        minimum_vehicle_speed_mps=0.5, min_track_history=3, cooldown_seconds=30,
        severity="high", confidence_threshold=0.4, cooldown=Cooldown(),
    )
    out = []
    for i in range(10):
        t = advance(base_time, i * 0.1)
        person = make_obs(1, (100, 100), t, "person", ground_m=(5 + i * 0.1, 3.0), velocity_mps=(1.0, 0.0))
        veh = make_obs(2, (200, 100), t, "forklift", ground_m=(5 + i * 0.1, 11.0), velocity_mps=(1.0, 0.0))
        out += rule.update([person, veh], t)
    assert out == []
