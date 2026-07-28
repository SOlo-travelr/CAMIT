"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CameraCreate(BaseModel):
    camera_id: str
    name: str
    source_kind: str = "file"
    source_uri: str


class CameraOut(BaseModel):
    camera_id: str
    name: str
    source_kind: str
    source_uri: str
    enabled: bool


class CalibrationCreate(BaseModel):
    image_points: list[list[float]]
    world_points_m: list[list[float]]
    operator: str | None = None


class CalibrationOut(BaseModel):
    camera_id: str
    reprojection_error_px: float
    is_metric: bool
    num_points: int


class ZoneCreate(BaseModel):
    zone_id: str
    camera_id: str | None = None
    polygon: list[list[float]]


class PolicyTranslateRequest(BaseModel):
    text: str


class PolicyValidateResponse(BaseModel):
    outcome: str
    errors: list[str] = []
    warnings: list[str] = []


class IncidentOut(BaseModel):
    incident_id: str
    event_type: str
    camera_id: str
    start_time: datetime
    end_time: datetime
    severity: str
    confidence: float
    track_ids: list[int]
    snapshot_uri: str | None
    clip_uri: str | None
    review_status: str


class FeedbackCreate(BaseModel):
    reviewer_id: str
    verdict: str
    correct_event_type: str | None = None
    severity_assessment: str | None = None
    usefulness: int | None = None
    comments: str | None = None
