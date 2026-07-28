"""Per-camera worker: builds a pipeline from config and runs it with health
tracking and reconnection handled by the underlying video source."""

from __future__ import annotations

import json
from pathlib import Path

from apps.worker.pipeline import CameraPipeline
from sentinel.config import AppConfig
from sentinel.events.state import Zone
from sentinel.observability.logging import get_logger
from sentinel.observability.metrics import CAMERA_UP
from sentinel.perception.calibration import compute_homography
from sentinel.perception.detector import SyntheticDetector, UltralyticsDetector
from sentinel.policies.compiler import load_policies_dir
from sentinel.storage.database import Database
from sentinel.storage.object_store import LocalObjectStore
from sentinel.video.source import create_video_source

logger = get_logger(__name__)


def build_pipeline_from_sidecar(
    sidecar_path: str | Path, video_path: str | Path, config: AppConfig,
    database: Database | None = None, object_store: LocalObjectStore | None = None,
) -> CameraPipeline:
    """Build a pipeline using a ground-truth sidecar (synthetic detector).

    Used for offline replay/demo; production uses a model detector instead.
    """
    sidecar = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
    camera_id = sidecar["camera_id"]
    zones = {
        zid: Zone(zone_id=zid, polygon=[tuple(p) for p in poly], camera_id=camera_id)
        for zid, poly in sidecar.get("zones", {}).items()
    }
    calibration = None
    if sidecar.get("calibration"):
        c = sidecar["calibration"]
        calibration = compute_homography(
            [tuple(p) for p in c["image_points"]],
            [tuple(p) for p in c["world_points_m"]],
            camera_id=camera_id,
            resolution=(sidecar["width"], sidecar["height"]),
        )
    policies = load_policies_dir("configs/policies")
    scoped = []
    for p in policies:
        p2 = p.model_copy(deep=True)
        p2.scope.camera_ids = [camera_id]
        scoped.append(p2)

    source = create_video_source(camera_id, "file", str(video_path))
    detector = SyntheticDetector(sidecar_path, confidence_floor=0.0)
    CAMERA_UP.labels(camera_id).set(1)
    return CameraPipeline(
        camera_id=camera_id, source=source, detector=detector, config=config,
        zones=zones, policies=scoped, calibration=calibration,
        database=database, object_store=object_store,
    )


def build_detector(config: AppConfig, sidecar_path: str | Path | None = None):
    if config.detector.backend == "synthetic":
        if sidecar_path is None:
            raise ValueError("synthetic detector requires a sidecar path")
        return SyntheticDetector(sidecar_path, confidence_floor=0.0)
    return UltralyticsDetector(
        model=config.detector.model, confidence=config.detector.confidence,
        classes=config.detector.classes,
    )
