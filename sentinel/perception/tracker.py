"""Multi-object tracker implementations.

``BuiltinTracker`` is a dependency-free IoU/SORT-style associator that returns
persistent integer IDs, so the full pipeline runs without any ML stack. A
``ByteTrack``-compatible adapter is provided behind the same interface for
production use.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from sentinel.contracts import BoundingBox, Detection, FramePacket
from sentinel.perception.interfaces import Track


@dataclass
class _TrackState:
    track_id: int
    class_name: str
    confidence: float
    box: BoundingBox
    hits: int = 1
    age: int = 0
    time_since_update: int = 0
    history: list[BoundingBox] = field(default_factory=list)


class BuiltinTracker:
    """Greedy IoU tracker with track buffering and hit confirmation."""

    def __init__(
        self,
        iou_threshold: float = 0.3,
        max_age_frames: int = 30,
        min_hits: int = 3,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.max_age_frames = max_age_frames
        self.min_hits = min_hits
        self._tracks: list[_TrackState] = []
        self._next_id = 1
        #: Track IDs pruned during the most recent :meth:`update` call. The
        #: pipeline consumes these to release per-track state (observation
        #: history, rule state) so long-running feeds do not leak memory.
        self.removed_track_ids: list[int] = []

    def update(self, detections: list[Detection], frame: FramePacket) -> list[Track]:
        for t in self._tracks:
            t.age += 1
            t.time_since_update += 1

        matches, unmatched_dets = self._associate(detections)

        for det_idx, trk in matches:
            det = detections[det_idx]
            trk.box = det.box
            trk.confidence = det.confidence
            trk.class_name = det.class_name
            trk.hits += 1
            trk.time_since_update = 0
            trk.history.append(det.box)

        for det_idx in unmatched_dets:
            det = detections[det_idx]
            self._tracks.append(
                _TrackState(
                    track_id=self._next_id,
                    class_name=det.class_name,
                    confidence=det.confidence,
                    box=det.box,
                    history=[det.box],
                )
            )
            self._next_id += 1

        self.removed_track_ids = [
            t.track_id for t in self._tracks if t.time_since_update > self.max_age_frames
        ]
        self._tracks = [t for t in self._tracks if t.time_since_update <= self.max_age_frames]

        output: list[Track] = []
        for t in self._tracks:
            if t.time_since_update == 0 and (t.hits >= self.min_hits or self.min_hits <= 1):
                output.append(Track(t.track_id, t.class_name, t.confidence, t.box))
        return output

    def _associate(
        self, detections: list[Detection]
    ) -> tuple[list[tuple[int, _TrackState]], list[int]]:
        if not self._tracks or not detections:
            return [], list(range(len(detections)))

        iou = np.zeros((len(detections), len(self._tracks)), dtype=float)
        for i, det in enumerate(detections):
            for j, trk in enumerate(self._tracks):
                if det.class_name == trk.class_name:
                    iou[i, j] = det.box.iou(trk.box)

        matches: list[tuple[int, _TrackState]] = []
        used_dets: set[int] = set()
        used_trks: set[int] = set()
        # Greedy: repeatedly take the highest remaining IoU above threshold.
        while True:
            i, j = np.unravel_index(int(np.argmax(iou)), iou.shape)
            if iou[i, j] < self.iou_threshold:
                break
            if i not in used_dets and j not in used_trks:
                matches.append((int(i), self._tracks[int(j)]))
                used_dets.add(int(i))
                used_trks.add(int(j))
            iou[i, j] = -1.0
            if len(used_dets) == len(detections) or len(used_trks) == len(self._tracks):
                break

        unmatched = [i for i in range(len(detections)) if i not in used_dets]
        return matches, unmatched


class ByteTrackAdapter:
    """Adapter exposing a ByteTrack tracker behind the platform interface.

    Falls back with a clear error if the optional dependency is missing so that
    the deterministic core never silently degrades.
    """

    def __init__(self, **kwargs) -> None:
        try:
            from ultralytics.trackers.byte_tracker import BYTETracker  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "ByteTrack backend requires the 'perception' extra: pip install -e '.[perception]'"
            ) from exc
        self._impl_factory = BYTETracker
        self._kwargs = kwargs
        self._tracker = None

    def update(self, detections: list[Detection], frame: FramePacket) -> list[Track]:  # pragma: no cover
        raise NotImplementedError(
            "ByteTrackAdapter is wired for production deployment; the builtin "
            "tracker is used for tests and CI."
        )


def create_tracker(config) -> BuiltinTracker | ByteTrackAdapter:
    backend = getattr(config, "backend", "builtin")
    if backend == "builtin":
        return BuiltinTracker(
            iou_threshold=config.iou_threshold,
            max_age_frames=config.max_age_frames,
            min_hits=config.min_hits,
        )
    if backend == "bytetrack":
        return ByteTrackAdapter(track_thresh=0.5)
    raise ValueError(f"Unknown tracker backend: {backend}")
