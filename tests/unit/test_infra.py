"""Unit tests for calibration, tracker and incident dedup."""

from __future__ import annotations

from datetime import UTC, timedelta

from sentinel.contracts import BoundingBox, Detection, EventCandidate, FramePacket
from sentinel.incidents.manager import IncidentManager
from sentinel.perception.calibration import compute_homography
from sentinel.perception.tracker import BuiltinTracker


def test_homography_roundtrip():
    image_points = [(0, 720), (1280, 720), (1280, 0), (0, 0)]
    world_points = [(0.0, 0.0), (25.6, 0.0), (25.6, 14.4), (0.0, 14.4)]
    calib = compute_homography(image_points, world_points, "cam", (1280, 720))
    assert calib.reprojection_error_px < 1.0
    assert calib.is_metric
    x, y = calib.to_world((640, 720))
    assert abs(x - 12.8) < 0.2
    assert abs(y - 0.0) < 0.2


def test_tracker_stable_ids():
    import numpy as np

    tracker = BuiltinTracker(iou_threshold=0.3, max_age_frames=10, min_hits=1)
    ids = set()
    for i in range(10):
        box = BoundingBox(10 + i, 10, 30 + i, 50)
        frame = FramePacket("cam", i, _t(i), np.zeros((60, 60, 3), np.uint8), 60, 60, 15)
        tracks = tracker.update([Detection("person", 0.9, box)], frame)
        assert len(tracks) == 1
        ids.add(tracks[0].track_id)
    assert len(ids) == 1  # single persistent id


def test_incident_dedup_merges_related_candidates():
    mgr = IncidentManager(cooldown_window_seconds=30)
    t0 = _t(0)
    c1 = EventCandidate("restricted_zone", "cam", t0, [1], 0.9, "medium", {"zone_id": "z"}, "p")
    c2 = EventCandidate(
        "restricted_zone", "cam", t0 + timedelta(seconds=2), [1], 0.95, "medium",
        {"zone_id": "z"}, "p",
    )
    first = mgr.ingest(c1)
    second = mgr.ingest(c2)
    assert first is not None
    assert second is None  # merged into the same incident
    assert first.confidence == 0.95


def _t(i: int):
    from datetime import datetime

    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=i / 15)
