"""End-to-end camera pipeline: decode -> detect -> track -> observe -> events ->
incident evidence -> persistence.

This is the deterministic runtime. It has no LLM dependency and continues to
function if the dashboard, alert integrations or internet are unavailable.
"""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from sentinel.config import AppConfig
from sentinel.contracts import EventCandidate, Incident
from sentinel.events.engine import EventEngine
from sentinel.events.state import Zone
from sentinel.incidents.clip_writer import write_clip
from sentinel.incidents.manager import IncidentManager
from sentinel.incidents.snapshot import save_snapshot
from sentinel.observability.logging import get_logger
from sentinel.observability.metrics import (
    DETECTIONS,
    EVENTS_EMITTED,
    FRAMES_DROPPED,
    FRAMES_PROCESSED,
    INCIDENTS_CREATED,
    PIPELINE_LATENCY,
)
from sentinel.perception.calibration import CameraCalibration
from sentinel.perception.observation import ObservationBuilder
from sentinel.perception.tracker import create_tracker
from sentinel.storage.database import Database
from sentinel.storage.object_store import LocalObjectStore
from sentinel.storage.repositories import IncidentRepository
from sentinel.video.frame_sampler import FrameSampler
from sentinel.video.ring_buffer import RingBuffer
from sentinel.video.source import VideoSource

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    incidents: list[Incident] = field(default_factory=list)
    frames: int = 0


class CameraPipeline:
    def __init__(
        self,
        camera_id: str,
        source: VideoSource,
        detector,
        config: AppConfig,
        zones: dict[str, Zone],
        policies: list,
        calibration: CameraCalibration | None = None,
        database: Database | None = None,
        object_store: LocalObjectStore | None = None,
    ) -> None:
        self.camera_id = camera_id
        self.source = source
        self.detector = detector
        self.config = config
        self.calibration = calibration
        self.database = database
        self.object_store = object_store
        self.tracker = create_tracker(config.tracker)
        self.builder = ObservationBuilder()
        self.engine = EventEngine(
            camera_id=camera_id, zones=zones, policies=policies, calibration=calibration,
            max_tracking_gap_seconds=config.tracker.max_tracking_gap_seconds,
            min_track_history=config.tracker.min_hits,
        )
        self.sampler = FrameSampler(config.video.decode_fps, config.detector.inference_fps)
        self.ring = RingBuffer(config.video.ring_buffer_seconds, config.video.decode_fps)
        self.incidents = IncidentManager(config.event_engine.default_cooldown_seconds)
        self.zones = zones
        self._last_observations: list = []

    def run(self, max_frames: int | None = None) -> PipelineResult:
        result = PipelineResult()
        for frame in self.source.frames():
            self.ring.push(frame)
            FRAMES_PROCESSED.labels(self.camera_id).inc()
            result.frames += 1
            if not self.sampler.accept(frame):
                continue

            try:
                self._process_frame(frame, result)
            except Exception:
                # A single malformed/corrupt frame must never take down a live
                # feed. Log, count it, and keep processing the stream.
                FRAMES_DROPPED.labels(self.camera_id).inc()
                logger.exception(
                    "frame processing failed; skipping",
                    extra={"extra_fields": {
                        "camera_id": self.camera_id, "frame_id": frame.frame_id,
                    }},
                )

            if max_frames is not None and result.frames >= max_frames:
                break
        return result

    def _process_frame(self, frame, result: PipelineResult) -> None:
        t0 = time.perf_counter()
        detections = self.detector.predict(frame.image, frame)
        for d in detections:
            DETECTIONS.labels(self.camera_id, d.class_name).inc()
        tracks = self.tracker.update(detections, frame)
        observations = self.builder.build(
            self.camera_id, frame.timestamp, tracks, self.calibration
        )
        self._last_observations = observations
        candidates = self.engine.update(observations, now=frame.timestamp)
        PIPELINE_LATENCY.labels(self.camera_id).observe(time.perf_counter() - t0)

        # Release per-track state for tracks the tracker has dropped so long
        # feeds stay bounded in memory.
        for track_id in getattr(self.tracker, "removed_track_ids", []):
            self.builder.forget(track_id)
            self.engine.forget(track_id)

        for candidate in candidates:
            EVENTS_EMITTED.labels(self.camera_id, candidate.event_type).inc()
            incident = self.incidents.ingest(candidate)
            if incident is not None:
                self._finalize_incident(incident, candidate, frame)
                result.incidents.append(incident)

    def _finalize_incident(
        self, incident: Incident, candidate: EventCandidate, frame
    ) -> None:
        if self.object_store is not None:
            try:
                tmp = Path(tempfile.gettempdir())
                snap_path = save_snapshot(
                    tmp / f"{incident.incident_id}.jpg",
                    frame.image,
                    self._last_observations,
                    {z.zone_id: z.polygon for z in self.zones.values()},
                    set(candidate.involved_track_ids),
                )
                incident.evidence.snapshot_uri = self.object_store.put(
                    f"incidents/{incident.incident_id}/snapshot.jpg", snap_path
                )
                clip_frames = self.ring.snapshot()
                if clip_frames:
                    clip_path = write_clip(
                        tmp / f"{incident.incident_id}.mp4", clip_frames
                    )
                    incident.evidence.clip_uri = self.object_store.put(
                        f"incidents/{incident.incident_id}/clip.mp4", clip_path
                    )
            except Exception:
                logger.exception("Failed to write incident evidence")

        if self.database is not None:
            with self.database.session() as session:
                IncidentRepository(session).create(incident)

        INCIDENTS_CREATED.labels(self.camera_id, incident.event_type).inc()
        logger.info(
            "incident created",
            extra={"extra_fields": {
                "incident_id": incident.incident_id,
                "event_type": incident.event_type,
                "camera_id": self.camera_id,
            }},
        )
