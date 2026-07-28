"""Camera calibration: pixel <-> ground-plane metric mapping via homography."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np

Vec = tuple[float, float]


@dataclass
class CameraCalibration:
    """Planar homography mapping image pixels to metric ground coordinates."""

    camera_id: str
    homography: np.ndarray  # 3x3 pixel -> metres
    reprojection_error_px: float
    image_points: list[Vec]
    world_points_m: list[Vec]
    resolution: tuple[int, int]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    operator: str | None = None
    max_allowed_error_px: float = 8.0

    @property
    def is_metric(self) -> bool:
        """True if this calibration is good enough to enable metric distance rules."""
        return self.reprojection_error_px <= self.max_allowed_error_px

    def to_world(self, pixel: Vec) -> Vec:
        """Map an image pixel to metric ground coordinates."""
        p = np.array([pixel[0], pixel[1], 1.0])
        w = self.homography @ p
        if abs(w[2]) < 1e-12:
            return (float("nan"), float("nan"))
        return (float(w[0] / w[2]), float(w[1] / w[2]))


def compute_homography(
    image_points: list[Vec],
    world_points_m: list[Vec],
    camera_id: str,
    resolution: tuple[int, int],
    operator: str | None = None,
    max_allowed_error_px: float = 8.0,
) -> CameraCalibration:
    """Compute a ground-plane homography from >= 4 correspondences.

    Uses OpenCV's RANSAC homography and reports mean reprojection error (in the
    image plane, obtained by mapping world points back through the inverse).
    """
    if len(image_points) < 4 or len(world_points_m) < 4:
        raise ValueError("At least four point correspondences are required")
    if len(image_points) != len(world_points_m):
        raise ValueError("image_points and world_points_m must have equal length")

    import cv2  # local import; keeps module importable without OpenCV at doc time

    src = np.asarray(image_points, dtype=np.float64)
    dst = np.asarray(world_points_m, dtype=np.float64)
    H, _ = cv2.findHomography(src, dst, method=cv2.RANSAC)
    if H is None:
        raise ValueError("Homography could not be estimated from the given points")

    # Reprojection error measured back in pixels using the inverse homography.
    H_inv = np.linalg.inv(H)
    errors = []
    for (px, py), (wx, wy) in zip(image_points, world_points_m, strict=False):
        proj = H_inv @ np.array([wx, wy, 1.0])
        proj = proj / proj[2]
        errors.append(float(np.hypot(proj[0] - px, proj[1] - py)))
    reproj = float(np.mean(errors)) if errors else float("inf")

    return CameraCalibration(
        camera_id=camera_id,
        homography=H,
        reprojection_error_px=reproj,
        image_points=list(image_points),
        world_points_m=list(world_points_m),
        resolution=resolution,
        operator=operator,
        max_allowed_error_px=max_allowed_error_px,
    )
