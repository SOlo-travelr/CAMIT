"""Zone management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_database
from apps.api.schemas import ZoneCreate
from sentinel.storage.database import Database
from sentinel.storage.models import ZoneRow

router = APIRouter(prefix="/zones", tags=["zones"])


@router.post("")
def create_zone(body: ZoneCreate, db: Database = Depends(get_database)) -> dict:
    with db.session() as session:
        row = session.get(ZoneRow, body.zone_id)
        if row is None:
            row = ZoneRow(id=body.zone_id, camera_id=body.camera_id, polygon=body.polygon)
            session.add(row)
        else:
            row.camera_id = body.camera_id
            row.polygon = body.polygon
    return {"zone_id": body.zone_id, "stored": True}


@router.get("")
def list_zones(db: Database = Depends(get_database)) -> list[dict]:
    from sqlalchemy import select

    with db.session() as session:
        return [
            {"zone_id": z.id, "camera_id": z.camera_id, "polygon": z.polygon}
            for z in session.scalars(select(ZoneRow))
        ]
