"""Writes pre/post-event incident clips from buffered + live frames."""

from __future__ import annotations

from pathlib import Path

import cv2

from sentinel.contracts import FramePacket


def write_clip(path: str | Path, frames: list[FramePacket], fps: float | None = None) -> Path:
    """Encode a list of frames into an MP4 clip.

    Frames must share the same resolution. Returns the output path.
    """
    if not frames:
        raise ValueError("Cannot write an empty clip")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    height, width = frames[0].image.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out), fourcc, fps or frames[0].source_fps, (width, height))
    try:
        for f in frames:
            writer.write(f.image)
    finally:
        writer.release()
    return out
