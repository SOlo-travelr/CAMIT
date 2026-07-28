"""Frame sampling: decouple detector inference rate from decode rate."""

from __future__ import annotations

from sentinel.contracts import FramePacket


class FrameSampler:
    """Accepts frames at decode rate, admits them at the target inference rate."""

    def __init__(self, decode_fps: float, target_fps: float) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be positive")
        self.decode_fps = decode_fps
        self.target_fps = min(target_fps, decode_fps)
        self._interval = decode_fps / self.target_fps
        self._counter = 0.0

    def accept(self, frame: FramePacket) -> bool:
        """Return True when this frame should be run through detection."""
        self._counter += 1.0
        if self._counter >= self._interval:
            self._counter -= self._interval
            return True
        return False
