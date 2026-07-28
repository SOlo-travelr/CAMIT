"""Core typed data contracts shared across the platform.

These are the single source of truth for what flows through the deterministic
pipeline: ``decode -> detect -> track -> observe -> evaluate -> emit``.

All timestamps are timezone-aware UTC ``datetime`` objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    """Supported event types for the industrial-safety MVP."""

    RESTRICTED_ZONE = "restricted_zone"
    LOITERING = "loitering"
    PROXIMITY = "proximity"
    COLLISION_RISK = "collision_risk"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class Verdict(str, Enum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    CORRECT_EVENT_WRONG_SEVERITY = "correct_event_wrong_severity"
    CORRECT_OBSERVATION_WRONG_EVENT_TYPE = "correct_observation_wrong_event_type"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CAMERA_QUALITY_FAILURE = "camera_quality_failure"
    DUPLICATE_INCIDENT = "duplicate_incident"


# ---------------------------------------------------------------------------
# Frame / detection primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FramePacket:
    """A single decoded frame flowing through the pipeline."""

    camera_id: str
    frame_id: int
    timestamp: datetime
    image: np.ndarray
    width: int
    height: int
    source_fps: float


@dataclass(frozen=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    @property
    def centroid(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def bottom_center(self) -> tuple[float, float]:
        """Approximate ground-contact point for people / vehicles."""
        return ((self.x1 + self.x2) / 2.0, self.y2)

    def iou(self, other: BoundingBox) -> float:
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)
        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
        inter = iw * ih
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float
    box: BoundingBox


# ---------------------------------------------------------------------------
# Tracking / observation
# ---------------------------------------------------------------------------


@dataclass
class TrackObservation:
    """A tracked object's state at one instant, enriched with world geometry."""

    camera_id: str
    track_id: int
    timestamp: datetime
    class_name: str
    confidence: float
    box: BoundingBox
    centroid_px: tuple[float, float]
    ground_point_px: tuple[float, float]
    ground_point_m: tuple[float, float] | None = None
    velocity_mps: tuple[float, float] | None = None
    velocity_px: tuple[float, float] | None = None


# ---------------------------------------------------------------------------
# Events / incidents
# ---------------------------------------------------------------------------


@dataclass
class EventCandidate:
    event_type: str
    camera_id: str
    timestamp: datetime
    involved_track_ids: list[int]
    confidence: float
    severity: str
    evidence: dict[str, Any]
    policy_id: str

    def dedup_key(self, cooldown_window: int) -> tuple:
        """Key used to collapse related candidates into one incident."""
        window = int(self.timestamp.timestamp() // max(1, cooldown_window))
        return (
            self.camera_id,
            self.event_type,
            tuple(sorted(self.involved_track_ids)),
            window,
        )


@dataclass
class IncidentEvidence:
    snapshot_uri: str | None = None
    clip_uri: str | None = None
    raw_clip_uri: str | None = None
    observations: dict[str, Any] = field(default_factory=dict)
    triggered_conditions: list[str] = field(default_factory=list)


@dataclass
class Incident:
    incident_id: str
    event_type: str
    camera_id: str
    start_time: datetime
    end_time: datetime
    severity: str
    confidence: float
    track_ids: list[int]
    policy_id: str
    evidence: IncidentEvidence = field(default_factory=IncidentEvidence)
    review_status: str = ReviewStatus.UNREVIEWED.value


@dataclass
class OperatorFeedback:
    incident_id: str
    reviewer_id: str
    verdict: str
    correct_event_type: str | None = None
    severity_assessment: str | None = None
    usefulness: int | None = None
    comments: str | None = None


@dataclass
class ModelVersion:
    model_name: str
    model_version: str
    git_commit: str | None = None
    detector_threshold: float | None = None
    tracker: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationRun:
    run_id: str
    dataset_version: str
    git_commit: str | None
    model_version: str | None
    thresholds: dict[str, Any]
    metrics: dict[str, Any]
    created_at: datetime
