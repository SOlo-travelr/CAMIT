"""Unit tests for policy schema validation and the compiler."""

from __future__ import annotations

import copy

from sentinel.policies.validator import (
    ValidationContext,
    ValidationOutcome,
    validate_policy,
)

VALID = {
    "policy_id": "p1",
    "name": "test",
    "scope": {"camera_ids": ["cam1"], "schedule": {"days": ["mon"], "start": "00:00", "end": "23:59"}},
    "subjects": {"primary": {"class": "person"}, "secondary": {"class": "forklift"}},
    "zones": {"include": ["z1"]},
    "conditions": {"all": [
        {"type": "predicted_separation", "subjects": ["primary", "secondary"],
         "horizon_seconds": 3, "threshold_meters": 1.0},
    ]},
    "event": {"type": "collision_risk", "cooldown_seconds": 30, "confidence_threshold": 0.5,
              "severity": "high"},
}


def _ctx(calibrated=True):
    return ValidationContext(
        camera_ids={"cam1"},
        zone_ids={"z1"},
        calibrated_camera_ids={"cam1"} if calibrated else set(),
    )


def test_valid_policy_accepted():
    res = validate_policy(copy.deepcopy(VALID), _ctx())
    assert res.outcome == ValidationOutcome.ACCEPTED
    assert res.policy is not None


def test_unknown_camera_rejected():
    bad = copy.deepcopy(VALID)
    bad["scope"]["camera_ids"] = ["ghost"]
    res = validate_policy(bad, _ctx())
    assert res.outcome == ValidationOutcome.REJECTED
    assert any("Unknown camera" in e for e in res.errors)


def test_unknown_zone_rejected():
    bad = copy.deepcopy(VALID)
    bad["zones"]["include"] = ["nope"]
    res = validate_policy(bad, _ctx())
    assert res.outcome == ValidationOutcome.REJECTED


def test_negative_duration_rejected():
    bad = copy.deepcopy(VALID)
    bad["conditions"]["all"][0]["horizon_seconds"] = -1
    res = validate_policy(bad, _ctx())
    assert res.outcome == ValidationOutcome.REJECTED


def test_uncalibrated_metric_policy_warns():
    res = validate_policy(copy.deepcopy(VALID), _ctx(calibrated=False))
    assert res.outcome == ValidationOutcome.ACCEPTED_WITH_WARNINGS
    assert any("calibrat" in w.lower() for w in res.warnings)


def test_unsupported_class_rejected():
    bad = copy.deepcopy(VALID)
    bad["subjects"]["primary"]["class"] = "dragon"
    res = validate_policy(bad, _ctx())
    assert res.outcome == ValidationOutcome.REJECTED


def test_predicted_separation_requires_secondary():
    bad = copy.deepcopy(VALID)
    bad["subjects"].pop("secondary")
    res = validate_policy(bad, _ctx())
    assert res.outcome == ValidationOutcome.REJECTED
