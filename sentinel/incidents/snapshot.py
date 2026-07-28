"""Annotated snapshot generation for incidents."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from sentinel.contracts import TrackObservation

_CLASS_COLORS = {
    "person": (0, 200, 0),
    "forklift": (0, 140, 255),
    "car": (255, 140, 0),
    "truck": (255, 140, 0),
}


def annotate_frame(
    image: np.ndarray,
    observations: list[TrackObservation],
    zones: dict[str, list[tuple[float, float]]] | None = None,
    highlight_track_ids: set[int] | None = None,
) -> np.ndarray:
    canvas = image.copy()
    highlight = highlight_track_ids or set()

    if zones:
        for _zid, poly in zones.items():
            pts = np.array(poly, dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(canvas, [pts], isClosed=True, color=(0, 0, 255), thickness=2)

    for obs in observations:
        color = _CLASS_COLORS.get(obs.class_name, (200, 200, 200))
        thickness = 3 if obs.track_id in highlight else 2
        x1, y1, x2, y2 = (int(v) for v in obs.box.as_tuple())
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)
        label = f"{obs.class_name}#{obs.track_id} {obs.confidence:.2f}"
        cv2.putText(
            canvas, label, (x1, max(0, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
        )
        gx, gy = (int(v) for v in obs.ground_point_px)
        cv2.circle(canvas, (gx, gy), 4, color, -1)
    return canvas


def save_snapshot(
    path: str | Path,
    image: np.ndarray,
    observations: list[TrackObservation],
    zones: dict[str, list[tuple[float, float]]] | None = None,
    highlight_track_ids: set[int] | None = None,
) -> Path:
    annotated = annotate_frame(image, observations, zones, highlight_track_ids)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), annotated)
    return out
