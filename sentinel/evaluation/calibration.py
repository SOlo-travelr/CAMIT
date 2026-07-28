"""Calibration evaluation: reprojection error and metric-readiness checks."""

from __future__ import annotations

from sentinel.perception.calibration import CameraCalibration


def calibration_report(calib: CameraCalibration) -> dict:
    return {
        "camera_id": calib.camera_id,
        "reprojection_error_px": round(calib.reprojection_error_px, 4),
        "max_allowed_error_px": calib.max_allowed_error_px,
        "is_metric": calib.is_metric,
        "num_points": len(calib.image_points),
    }
