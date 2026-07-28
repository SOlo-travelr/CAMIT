"""Operator feedback endpoint.

Feedback is stored for offline evaluation only; it never mutates live thresholds.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from apps.api.dependencies import get_database
from apps.api.schemas import FeedbackCreate
from sentinel.contracts import OperatorFeedback, Verdict
from sentinel.storage.database import Database
from sentinel.storage.repositories import FeedbackRepository, IncidentRepository

router = APIRouter(prefix="/incidents", tags=["feedback"])

_ALLOWED = {v.value for v in Verdict}


@router.post("/{incident_id}/feedback")
def add_feedback(
    incident_id: str, body: FeedbackCreate, db: Database = Depends(get_database)
) -> dict:
    if body.verdict not in _ALLOWED:
        raise HTTPException(status_code=422, detail=f"Invalid verdict. Allowed: {sorted(_ALLOWED)}")
    with db.session() as session:
        incidents = IncidentRepository(session)
        if incidents.get(incident_id) is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        FeedbackRepository(session).add(
            OperatorFeedback(
                incident_id=incident_id,
                reviewer_id=body.reviewer_id,
                verdict=body.verdict,
                correct_event_type=body.correct_event_type,
                severity_assessment=body.severity_assessment,
                usefulness=body.usefulness,
                comments=body.comments,
            )
        )
        status = "confirmed" if body.verdict == Verdict.TRUE_POSITIVE.value else "rejected"
        if body.verdict not in (Verdict.TRUE_POSITIVE.value, Verdict.FALSE_POSITIVE.value):
            status = "unreviewed"
        incidents.set_review_status(incident_id, status)
    return {"incident_id": incident_id, "stored": True, "review_status": status}
