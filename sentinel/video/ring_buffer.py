"""Per-camera ring buffer of recent frames for incident clip generation."""

from __future__ import annotations

from collections import deque

from sentinel.contracts import FramePacket


class RingBuffer:
    """Holds the most recent ``seconds`` of frames for pre-event footage."""

    def __init__(self, seconds: float, fps: float) -> None:
        self.seconds = seconds
        self.fps = fps
        self._buf: deque[FramePacket] = deque(maxlen=max(1, int(seconds * fps)))

    def push(self, frame: FramePacket) -> None:
        self._buf.append(frame)

    def snapshot(self) -> list[FramePacket]:
        """Return a copy of the currently buffered pre-event frames."""
        return list(self._buf)

    def __len__(self) -> int:
        return len(self._buf)
