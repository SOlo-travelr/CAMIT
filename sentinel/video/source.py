"""Video sources: file, webcam and RTSP, behind one interface.

Uses OpenCV for decoding. RTSP sources add reconnect handling. Each source
yields :class:`FramePacket` objects with monotonically increasing frame ids and
UTC timestamps.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import cv2

from sentinel.contracts import FramePacket
from sentinel.observability.logging import get_logger

logger = get_logger(__name__)


class VideoSource(Protocol):
    camera_id: str

    def frames(self) -> Iterator[FramePacket]:
        ...


class FileVideoSource:
    """Reads a video file. Timestamps are derived from the file's FPS so that
    offline runs are deterministic and reproducible."""

    def __init__(self, camera_id: str, path: str | Path, start_time: datetime | None = None) -> None:
        self.camera_id = camera_id
        self.path = str(path)
        self.start_time = start_time or datetime(2026, 1, 1, tzinfo=UTC)

    def frames(self) -> Iterator[FramePacket]:
        cap = cv2.VideoCapture(self.path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video file: {self.path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_id = 0
        try:
            while True:
                ok, image = cap.read()
                if not ok:
                    break
                ts = self.start_time.timestamp() + frame_id / fps
                yield FramePacket(
                    camera_id=self.camera_id,
                    frame_id=frame_id,
                    timestamp=datetime.fromtimestamp(ts, tz=UTC),
                    image=image,
                    width=width,
                    height=height,
                    source_fps=fps,
                )
                frame_id += 1
        finally:
            cap.release()


class WebcamVideoSource:
    def __init__(self, camera_id: str, index: int = 0) -> None:
        self.camera_id = camera_id
        self.index = index

    def frames(self) -> Iterator[FramePacket]:  # pragma: no cover - hardware dependent
        cap = cv2.VideoCapture(self.index)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open webcam index {self.index}")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_id = 0
        try:
            while True:
                ok, image = cap.read()
                if not ok:
                    break
                yield FramePacket(
                    camera_id=self.camera_id,
                    frame_id=frame_id,
                    timestamp=datetime.now(UTC),
                    image=image,
                    width=width,
                    height=height,
                    source_fps=fps,
                )
                frame_id += 1
        finally:
            cap.release()


class RtspVideoSource:
    """RTSP source with bounded reconnect attempts. Failures are surfaced, never
    silently swallowed, so camera health can reflect them."""

    def __init__(
        self,
        camera_id: str,
        uri: str,
        reconnect_seconds: float = 5.0,
        max_reconnects: int | None = None,
    ) -> None:
        self.camera_id = camera_id
        self.uri = uri
        self.reconnect_seconds = reconnect_seconds
        self.max_reconnects = max_reconnects

    def frames(self) -> Iterator[FramePacket]:  # pragma: no cover - network dependent
        frame_id = 0
        reconnects = 0
        while True:
            cap = cv2.VideoCapture(self.uri)
            if not cap.isOpened():
                reconnects += 1
                logger.warning(
                    "RTSP open failed", extra={"extra_fields": {"camera_id": self.camera_id}}
                )
                if self.max_reconnects is not None and reconnects > self.max_reconnects:
                    raise RuntimeError(f"RTSP camera {self.camera_id} unreachable")
                time.sleep(self.reconnect_seconds)
                continue
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            try:
                while True:
                    ok, image = cap.read()
                    if not ok:
                        logger.warning(
                            "RTSP read failed; reconnecting",
                            extra={"extra_fields": {"camera_id": self.camera_id}},
                        )
                        break
                    yield FramePacket(
                        camera_id=self.camera_id,
                        frame_id=frame_id,
                        timestamp=datetime.now(UTC),
                        image=image,
                        width=width,
                        height=height,
                        source_fps=fps,
                    )
                    frame_id += 1
            finally:
                cap.release()
            reconnects += 1
            if self.max_reconnects is not None and reconnects > self.max_reconnects:
                raise RuntimeError(f"RTSP camera {self.camera_id} lost")
            time.sleep(self.reconnect_seconds)


def create_video_source(camera_id: str, kind: str, uri: str, **kwargs) -> VideoSource:
    kind = kind.lower()
    if kind == "file":
        return FileVideoSource(camera_id, uri)
    if kind == "webcam":
        return WebcamVideoSource(camera_id, int(uri))
    if kind == "rtsp":
        return RtspVideoSource(camera_id, uri, **kwargs)
    raise ValueError(f"Unknown video source kind: {kind}")
