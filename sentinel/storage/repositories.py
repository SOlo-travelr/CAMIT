"""Repository helpers encapsulating persistence for domain objects."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from sentinel.contracts import Incident as IncidentDTO
from sentinel.contracts import OperatorFeedback
from sentinel.storage.models import (
    Camera,
    Incident,
    OperatorFeedbackRow,
    PolicyRow,
)


class IncidentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, incident: IncidentDTO) -> Incident:
        row = Incident(
            id=incident.incident_id,
            event_type=incident.event_type,
            camera_id=incident.camera_id,
            policy_id=incident.policy_id,
            start_time=incident.start_time,
            end_time=incident.end_time,
            severity=incident.severity,
            confidence=incident.confidence,
            track_ids=incident.track_ids,
            snapshot_uri=incident.evidence.snapshot_uri,
            clip_uri=incident.evidence.clip_uri,
            observations=incident.evidence.observations,
            triggered_conditions=incident.evidence.triggered_conditions,
            review_status=incident.review_status,
        )
        self.session.add(row)
        return row

    def get(self, incident_id: str) -> Incident | None:
        return self.session.get(Incident, incident_id)

    def list(
        self,
        camera_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[Incident]:
        stmt = select(Incident).order_by(Incident.start_time.desc()).limit(limit)
        if camera_id:
            stmt = stmt.where(Incident.camera_id == camera_id)
        if event_type:
            stmt = stmt.where(Incident.event_type == event_type)
        return list(self.session.scalars(stmt))

    def set_review_status(self, incident_id: str, status: str) -> None:
        row = self.get(incident_id)
        if row:
            row.review_status = status


class FeedbackRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, feedback: OperatorFeedback) -> OperatorFeedbackRow:
        row = OperatorFeedbackRow(
            incident_id=feedback.incident_id,
            reviewer_id=feedback.reviewer_id,
            verdict=feedback.verdict,
            correct_event_type=feedback.correct_event_type,
            severity_assessment=feedback.severity_assessment,
            usefulness=feedback.usefulness,
            comments=feedback.comments,
        )
        self.session.add(row)
        return row


class CameraRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, camera_id: str, name: str, source_kind: str, source_uri: str) -> Camera:
        row = self.session.get(Camera, camera_id)
        if row is None:
            row = Camera(
                id=camera_id, name=name, source_kind=source_kind,
                source_uri=source_uri, enabled=True,
            )
            self.session.add(row)
        else:
            row.name = name
            row.source_kind = source_kind
            row.source_uri = source_uri
        return row

    def list(self) -> list[Camera]:
        return list(self.session.scalars(select(Camera)))

    def get(self, camera_id: str) -> Camera | None:
        return self.session.get(Camera, camera_id)


class PolicyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, policy_id: str, name: str, definition: dict, enabled: bool = True) -> PolicyRow:
        row = self.session.get(PolicyRow, policy_id)
        if row is None:
            row = PolicyRow(id=policy_id, name=name, definition=definition, enabled=enabled)
            self.session.add(row)
        else:
            row.name = name
            row.definition = definition
            row.enabled = enabled
            row.version += 1
        return row

    def list(self) -> list[PolicyRow]:
        return list(self.session.scalars(select(PolicyRow)))
