"""Incident listing and clip retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from apps.api.dependencies import get_database, get_object_store
from apps.api.schemas import IncidentOut
from sentinel.storage.database import Database
from sentinel.storage.object_store import LocalObjectStore
from sentinel.storage.repositories import IncidentRepository

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _to_out(i) -> IncidentOut:
    return IncidentOut(
        incident_id=i.id, event_type=i.event_type, camera_id=i.camera_id,
        start_time=i.start_time, end_time=i.end_time, severity=i.severity,
        confidence=i.confidence, track_ids=i.track_ids, snapshot_uri=i.snapshot_uri,
        clip_uri=i.clip_uri, review_status=i.review_status,
    )


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    camera_id: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
    db: Database = Depends(get_database),
) -> list[IncidentOut]:
    with db.session() as session:
        rows = IncidentRepository(session).list(camera_id, event_type, limit)
        return [_to_out(r) for r in rows]


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str, db: Database = Depends(get_database)) -> IncidentOut:
    with db.session() as session:
        row = IncidentRepository(session).get(incident_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return _to_out(row)


@router.get("/{incident_id}/clip")
def get_clip(
    incident_id: str,
    db: Database = Depends(get_database),
    store: LocalObjectStore = Depends(get_object_store),
):
    with db.session() as session:
        row = IncidentRepository(session).get(incident_id)
        if row is None or not row.clip_uri:
            raise HTTPException(status_code=404, detail="Clip not available")
        path = store.uri_to_path(row.clip_uri)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Clip file missing")
    return FileResponse(path, media_type="video/mp4")
