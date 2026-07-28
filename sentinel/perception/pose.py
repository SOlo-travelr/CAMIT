"""Optional pose estimation stub.

Pose is not part of the four MVP events and is intentionally left as an
interface placeholder so it can be added later (e.g. for fall detection)
without touching the deterministic event path.
"""

from __future__ import annotations

from typing import Any


class PoseEstimator:  # pragma: no cover - placeholder for a later phase
    def predict(self, image: Any) -> list[Any]:
        raise NotImplementedError("Pose estimation is not enabled in the MVP scope")
