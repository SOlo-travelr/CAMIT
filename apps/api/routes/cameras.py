"""Camera and calibration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from apps.api.dependencies import get_database
from apps.api.schemas import (
    CalibrationCreate,
    CalibrationOut,
    CameraCreate,
    CameraOut,
)
from sentinel.perception.calibration import compute_homography
from sentinel.storage.database import Database
from sentinel.storage.models import Camera, CameraCalibrationRow
from sentinel.storage.repositories import CameraRepository

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.post("", response_model=CameraOut)
def create_camera(body: CameraCreate, db: Database = Depends(get_database)) -> CameraOut:
    with db.session() as session:
        row = CameraRepository(session).upsert(
            body.camera_id, body.name, body.source_kind, body.source_uri
        )
        return CameraOut(
            camera_id=row.id, name=row.name, source_kind=row.source_kind,
            source_uri=row.source_uri, enabled=row.enabled,
        )


@router.get("", response_model=list[CameraOut])
def list_cameras(db: Database = Depends(get_database)) -> list[CameraOut]:
    with db.session() as session:
        return [
            CameraOut(
                camera_id=c.id, name=c.name, source_kind=c.source_kind,
                source_uri=c.source_uri, enabled=c.enabled,
            )
            for c in CameraRepository(session).list()
        ]


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: str, db: Database = Depends(get_database)) -> CameraOut:
    with db.session() as session:
        c = CameraRepository(session).get(camera_id)
        if c is None:
            raise HTTPException(status_code=404, detail="Camera not found")
        return CameraOut(
            camera_id=c.id, name=c.name, source_kind=c.source_kind,
            source_uri=c.source_uri, enabled=c.enabled,
        )


@router.post("/{camera_id}/calibrations", response_model=CalibrationOut)
def create_calibration(
    camera_id: str, body: CalibrationCreate, db: Database = Depends(get_database)
) -> CalibrationOut:
    if len(body.image_points) < 4:
        raise HTTPException(status_code=422, detail="At least four points are required")
    with db.session() as session:
        camera = session.get(Camera, camera_id)
        resolution = (1920, 1080)
        calib = compute_homography(
            [tuple(p) for p in body.image_points],
            [tuple(p) for p in body.world_points_m],
            camera_id=camera_id,
            resolution=resolution,
            operator=body.operator,
        )
        row = CameraCalibrationRow(
            camera_id=camera_id,
            homography=calib.homography.tolist(),
            reprojection_error_px=calib.reprojection_error_px,
            image_points=body.image_points,
            world_points_m=body.world_points_m,
            resolution=list(resolution),
            operator=body.operator,
        )
        session.add(row)
        _ = camera  # existence not required for MVP calibration storage
        return CalibrationOut(
            camera_id=camera_id,
            reprojection_error_px=round(calib.reprojection_error_px, 4),
            is_metric=calib.is_metric,
            num_points=len(body.image_points),
        )


@router.get("/{camera_id}/calibrations/latest", response_model=CalibrationOut)
def latest_calibration(camera_id: str, db: Database = Depends(get_database)) -> CalibrationOut:
    from sqlalchemy import select

    with db.session() as session:
        stmt = (
            select(CameraCalibrationRow)
            .where(CameraCalibrationRow.camera_id == camera_id)
            .order_by(CameraCalibrationRow.created_at.desc())
            .limit(1)
        )
        row = session.scalars(stmt).first()
        if row is None:
            raise HTTPException(status_code=404, detail="No calibration for camera")
        return CalibrationOut(
            camera_id=camera_id,
            reprojection_error_px=round(row.reprojection_error_px, 4),
            is_metric=row.reprojection_error_px <= 8.0,
            num_points=len(row.image_points),
        )
