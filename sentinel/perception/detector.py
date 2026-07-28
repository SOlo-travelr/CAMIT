"""Object detector adapters.

- ``SyntheticDetector``: reads a ground-truth sidecar (``*.gt.json``) produced by
  ``scripts/generate_test_videos.py`` and returns per-frame detections with mild
  jitter. Requires no ML dependencies, so the whole pipeline is testable offline.
- ``UltralyticsDetector``: real YOLO model behind the same interface (optional).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from sentinel.contracts import BoundingBox, Detection, FramePacket


class SyntheticDetector:
    """Replays annotated boxes from a sidecar file keyed by frame id."""

    def __init__(
        self,
        sidecar_path: str | Path,
        confidence_floor: float = 0.6,
        jitter_px: float = 0.0,
        seed: int = 0,
    ) -> None:
        data = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
        self._frames: dict[int, list[dict]] = {
            int(k): v for k, v in data.get("frames", {}).items()
        }
        self.confidence_floor = confidence_floor
        self.jitter_px = jitter_px
        self._rng = np.random.default_rng(seed)

    def predict(self, image: np.ndarray, frame: FramePacket | None = None) -> list[Detection]:
        if frame is None:
            return []
        entries = self._frames.get(int(frame.frame_id), [])
        detections: list[Detection] = []
        for e in entries:
            x1, y1, x2, y2 = e["box"]
            if self.jitter_px:
                dx, dy = self._rng.normal(0, self.jitter_px, size=2)
                x1, x2 = x1 + dx, x2 + dx
                y1, y2 = y1 + dy, y2 + dy
            conf = float(e.get("confidence", 0.9))
            if conf < self.confidence_floor:
                continue
            detections.append(
                Detection(
                    class_name=e["class_name"],
                    confidence=conf,
                    box=BoundingBox(float(x1), float(y1), float(x2), float(y2)),
                )
            )
        return detections


class UltralyticsDetector:  # pragma: no cover - requires optional heavy dependency
    """Real YOLO detector behind the platform interface."""

    def __init__(self, model: str = "yolov8n.pt", confidence: float = 0.3, classes=None) -> None:
        try:
            from ultralytics import YOLO
        except Exception as exc:
            raise RuntimeError(
                "ultralytics backend requires: pip install -e '.[perception]'"
            ) from exc
        self._model = YOLO(model)
        self._confidence = confidence
        self._classes = set(classes) if classes else None

    def predict(self, image: np.ndarray, frame: FramePacket | None = None) -> list[Detection]:
        results = self._model.predict(image, conf=self._confidence, verbose=False)
        detections: list[Detection] = []
        for r in results:
            names = r.names
            for b in r.boxes:
                cls = names[int(b.cls)]
                if self._classes and cls not in self._classes:
                    continue
                x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
                detections.append(
                    Detection(cls, float(b.conf), BoundingBox(x1, y1, x2, y2))
                )
        return detections


def create_detector(config, sidecar_path: str | Path | None = None):
    backend = getattr(config, "backend", "synthetic")
    if backend == "synthetic":
        if sidecar_path is None:
            raise ValueError("synthetic detector requires a ground-truth sidecar path")
        return SyntheticDetector(sidecar_path, confidence_floor=0.0)
    if backend == "ultralytics":
        return UltralyticsDetector(
            model=config.model, confidence=config.confidence, classes=config.classes
        )
    raise ValueError(f"Unknown detector backend: {backend}")
