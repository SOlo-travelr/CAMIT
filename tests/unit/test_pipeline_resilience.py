"""Robustness guarantees added for real-world / low-quality feeds:

1. A single malformed frame must not tear down a live pipeline.
2. The tracker reports dropped track IDs so per-track state can be released.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import numpy as np

from sentinel.config import AppConfig
from sentinel.contracts import BoundingBox, Detection, FramePacket
from sentinel.perception.tracker import BuiltinTracker
from apps.worker.pipeline import CameraPipeline


class _FakeSource:
    camera_id = "cam"

    def __init__(self, n: int) -> None:
        self.n = n

    def frames(self) -> Iterator[FramePacket]:
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        for i in range(self.n):
            yield FramePacket(
                camera_id="cam",
                frame_id=i,
                timestamp=t0 + timedelta(seconds=i / 15.0),
                image=np.zeros((16, 16, 3), dtype=np.uint8),
                width=16,
                height=16,
                source_fps=15.0,
            )


class _ExplodingDetector:
    """Raises on one frame to simulate a corrupt/malformed frame."""

    def __init__(self, bad_frame_id: int) -> None:
        self.bad_frame_id = bad_frame_id
        self.calls = 0

    def predict(self, image, frame=None):
        self.calls += 1
        if frame is not None and frame.frame_id == self.bad_frame_id:
            raise ValueError("simulated corrupt frame")
        return []


def test_pipeline_survives_a_bad_frame():
    detector = _ExplodingDetector(bad_frame_id=3)
    config = AppConfig()
    # Admit every decoded frame so the corrupt frame is actually processed.
    config.detector.inference_fps = config.video.decode_fps
    pipeline = CameraPipeline(
        camera_id="cam",
        source=_FakeSource(n=10),
        detector=detector,
        config=config,
        zones={},
        policies=[],
        calibration=None,
    )

    result = pipeline.run()

    # Every frame was consumed even though frame 3 raised inside the detector.
    assert result.frames == 10
    assert detector.calls == 10


def test_builtin_tracker_reports_removed_tracks():
    tracker = BuiltinTracker(iou_threshold=0.3, max_age_frames=2, min_hits=1)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)

    def frame(i: int) -> FramePacket:
        return FramePacket("cam", i, t0, np.zeros((16, 16, 3), np.uint8), 16, 16, 15.0)

    det = Detection("person", 0.9, BoundingBox(0, 0, 10, 10))
    tracker.update([det], frame(0))
    assert tracker.removed_track_ids == []

    # No detections for several frames -> the track ages out and is reported
    # on the update that prunes it (the attribute holds only that update).
    removed: list[int] = []
    for i in range(1, 6):
        tracker.update([], frame(i))
        removed.extend(tracker.removed_track_ids)
    assert 1 in removed
