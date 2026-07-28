"""Abstract interfaces so model-specific code stays replaceable."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from sentinel.contracts import Detection, FramePacket


@runtime_checkable
class Detector(Protocol):
    """Object detector. Implementations must be swappable behind this interface."""

    def predict(self, image: np.ndarray, frame: FramePacket | None = None) -> list[Detection]:
        ...


@runtime_checkable
class Tracker(Protocol):
    """Multi-object tracker returning persistent integer track IDs."""

    def update(self, detections: list[Detection], frame: FramePacket) -> list[Track]:
        ...


class Track:
    """Lightweight tracker output before world-geometry enrichment."""

    __slots__ = ("track_id", "class_name", "confidence", "box")

    def __init__(self, track_id: int, class_name: str, confidence: float, box) -> None:
        self.track_id = track_id
        self.class_name = class_name
        self.confidence = confidence
        self.box = box
