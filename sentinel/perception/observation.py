"""Builds enriched :class:`TrackObservation` objects from raw tracks.

Computes the ground-contact point (bottom-center of the box), maps it to metric
world coordinates when a calibration is available, and estimates velocity from a
short per-track history using least-squares over smoothed positions.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime

from sentinel.contracts import TrackObservation
from sentinel.events.geometry import estimate_velocity
from sentinel.perception.calibration import CameraCalibration
from sentinel.perception.interfaces import Track


class ObservationBuilder:
    def __init__(self, history: int = 8) -> None:
        self._px_hist: dict[int, deque[tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=history)
        )
        self._m_hist: dict[int, deque[tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=history)
        )
        self._t_hist: dict[int, deque[float]] = defaultdict(lambda: deque(maxlen=history))

    def build(
        self,
        camera_id: str,
        timestamp: datetime,
        tracks: list[Track],
        calibration: CameraCalibration | None = None,
    ) -> list[TrackObservation]:
        ts = timestamp.timestamp()
        observations: list[TrackObservation] = []
        for trk in tracks:
            ground_px = trk.box.bottom_center
            centroid_px = trk.box.centroid
            ground_m = calibration.to_world(ground_px) if calibration else None

            self._px_hist[trk.track_id].append(ground_px)
            self._t_hist[trk.track_id].append(ts)
            if ground_m is not None:
                self._m_hist[trk.track_id].append(ground_m)

            times = list(self._t_hist[trk.track_id])
            vel_px = estimate_velocity(list(self._px_hist[trk.track_id]), times)
            vel_m = None
            if ground_m is not None and len(self._m_hist[trk.track_id]) >= 2:
                vel_m = estimate_velocity(list(self._m_hist[trk.track_id]), times)

            observations.append(
                TrackObservation(
                    camera_id=camera_id,
                    track_id=trk.track_id,
                    timestamp=timestamp,
                    class_name=trk.class_name,
                    confidence=trk.confidence,
                    box=trk.box,
                    centroid_px=centroid_px,
                    ground_point_px=ground_px,
                    ground_point_m=ground_m,
                    velocity_mps=vel_m,
                    velocity_px=vel_px,
                )
            )
        return observations

    def forget(self, track_id: int) -> None:
        self._px_hist.pop(track_id, None)
        self._m_hist.pop(track_id, None)
        self._t_hist.pop(track_id, None)
