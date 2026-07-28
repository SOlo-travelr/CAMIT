"""Watchdog: tracks camera health and flags stalled workers.

A camera is considered unhealthy if it has not produced a frame within the
configured timeout, so failures are visible rather than silent.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CameraHealth:
    camera_id: str
    last_frame_monotonic: float = field(default_factory=time.monotonic)
    status: str = "starting"
    detail: str | None = None

    def heartbeat(self) -> None:
        self.last_frame_monotonic = time.monotonic()
        self.status = "healthy"
        self.detail = None

    def check(self, timeout_s: float) -> str:
        if time.monotonic() - self.last_frame_monotonic > timeout_s:
            self.status = "stalled"
            self.detail = f"no frame for >{timeout_s}s"
        return self.status


class Watchdog:
    def __init__(self, timeout_s: float = 30.0) -> None:
        self.timeout_s = timeout_s
        self._cameras: dict[str, CameraHealth] = {}

    def register(self, camera_id: str) -> CameraHealth:
        health = CameraHealth(camera_id)
        self._cameras[camera_id] = health
        return health

    def statuses(self) -> dict[str, str]:
        return {cid: h.check(self.timeout_s) for cid, h in self._cameras.items()}
