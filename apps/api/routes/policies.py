"""Policy translation, validation and activation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_database
from apps.api.schemas import PolicyTranslateRequest, PolicyValidateResponse
from sentinel.policies.language_translator import LanguageTranslator
from sentinel.policies.validator import ValidationContext, validate_policy
from sentinel.storage.database import Database
from sentinel.storage.models import Camera, PolicyRow, ZoneRow
from sentinel.storage.repositories import PolicyRepository

router = APIRouter(prefix="/policies", tags=["policies"])


def _context(db: Database) -> ValidationContext:
    from sqlalchemy import select

    with db.session() as session:
        cameras = {c.id for c in session.scalars(select(Camera))}
        zones = {z.id for z in session.scalars(select(ZoneRow))}
        calibrated = set()  # populated from CameraCalibrationRow in a fuller build
    return ValidationContext(camera_ids=cameras, zone_ids=zones, calibrated_camera_ids=calibrated)


@router.post("/translate", response_model=PolicyValidateResponse)
def translate(body: PolicyTranslateRequest, db: Database = Depends(get_database)) -> PolicyValidateResponse:
    translator = LanguageTranslator()
    result = translator.translate(body.text, _context(db))
    return PolicyValidateResponse(
        outcome=result.validation.outcome.value,
        errors=result.validation.errors,
        warnings=result.validation.warnings,
    )


@router.post("/validate", response_model=PolicyValidateResponse)
def validate(raw: dict, db: Database = Depends(get_database)) -> PolicyValidateResponse:
    result = validate_policy(raw, _context(db))
    return PolicyValidateResponse(
        outcome=result.outcome.value, errors=result.errors, warnings=result.warnings
    )


@router.post("", response_model=PolicyValidateResponse)
def create_policy(raw: dict, db: Database = Depends(get_database)) -> PolicyValidateResponse:
    result = validate_policy(raw, _context(db))
    if result.accepted and result.policy is not None:
        with db.session() as session:
            PolicyRepository(session).upsert(
                result.policy.policy_id, result.policy.name,
                result.policy.model_dump(by_alias=True, mode="json"),
                enabled=result.policy.enabled,
            )
    return PolicyValidateResponse(
        outcome=result.outcome.value, errors=result.errors, warnings=result.warnings
    )


@router.get("")
def list_policies(db: Database = Depends(get_database)) -> list[dict]:
    with db.session() as session:
        return [
            {"policy_id": p.id, "name": p.name, "enabled": p.enabled, "version": p.version}
            for p in PolicyRepository(session).list()
        ]


@router.post("/{policy_id}/activate")
def activate(policy_id: str, db: Database = Depends(get_database)) -> dict:
    return _set_enabled(policy_id, True, db)


@router.post("/{policy_id}/deactivate")
def deactivate(policy_id: str, db: Database = Depends(get_database)) -> dict:
    return _set_enabled(policy_id, False, db)


def _set_enabled(policy_id: str, enabled: bool, db: Database) -> dict:
    with db.session() as session:
        row = session.get(PolicyRow, policy_id)
        if row is None:
            return {"policy_id": policy_id, "found": False}
        row.enabled = enabled
        return {"policy_id": policy_id, "enabled": enabled}
