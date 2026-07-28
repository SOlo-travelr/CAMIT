"""SQLAlchemy ORM models for platform metadata.

High-frequency frames are never stored here; clips/snapshots go to object
storage and only their URIs are persisted.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    source_kind: Mapped[str] = mapped_column(String, default="file")
    source_uri: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CameraCalibrationRow(Base):
    __tablename__ = "camera_calibrations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"))
    homography: Mapped[list] = mapped_column(JSON)
    reprojection_error_px: Mapped[float] = mapped_column(Float)
    image_points: Mapped[list] = mapped_column(JSON)
    world_points_m: Mapped[list] = mapped_column(JSON)
    resolution: Mapped[list] = mapped_column(JSON)
    operator: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ZoneRow(Base):
    __tablename__ = "zones"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    camera_id: Mapped[str | None] = mapped_column(ForeignKey("cameras.id"), nullable=True)
    polygon: Mapped[list] = mapped_column(JSON)


class PolicyRow(Base):
    __tablename__ = "policies"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    definition: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EventCandidateRow(Base):
    __tablename__ = "event_candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String)
    camera_id: Mapped[str] = mapped_column(String)
    policy_id: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    track_ids: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String)
    evidence: Mapped[dict] = mapped_column(JSON)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), nullable=True)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String)
    camera_id: Mapped[str] = mapped_column(String)
    policy_id: Mapped[str] = mapped_column(String)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    track_ids: Mapped[list] = mapped_column(JSON)
    snapshot_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    clip_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    observations: Mapped[dict] = mapped_column(JSON, default=dict)
    triggered_conditions: Mapped[list] = mapped_column(JSON, default=list)
    review_status: Mapped[str] = mapped_column(String, default="unreviewed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    feedback: Mapped[list[OperatorFeedbackRow]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class OperatorFeedbackRow(Base):
    __tablename__ = "operator_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    reviewer_id: Mapped[str] = mapped_column(String)
    verdict: Mapped[str] = mapped_column(String)
    correct_event_type: Mapped[str | None] = mapped_column(String, nullable=True)
    severity_assessment: Mapped[str | None] = mapped_column(String, nullable=True)
    usefulness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    incident: Mapped[Incident] = relationship(back_populates="feedback")


class CameraHealthRow(Base):
    __tablename__ = "camera_health"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ModelVersionRow(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String)
    model_version: Mapped[str] = mapped_column(String)
    git_commit: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EvaluationRunRow(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset_version: Mapped[str] = mapped_column(String)
    git_commit: Mapped[str | None] = mapped_column(String, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    thresholds: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
