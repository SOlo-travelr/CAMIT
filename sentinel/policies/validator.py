"""Policy validation against the runtime context (cameras, zones, calibration)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pydantic import ValidationError

from sentinel.policies.models import ConditionType, Policy


class ValidationOutcome(str, Enum):
    ACCEPTED = "Policy accepted"
    ACCEPTED_WITH_WARNINGS = "Policy accepted with warnings"
    REJECTED = "Policy rejected"


@dataclass
class ValidationContext:
    """Known runtime entities the policy is allowed to reference."""

    camera_ids: set[str] = field(default_factory=set)
    zone_ids: set[str] = field(default_factory=set)
    calibrated_camera_ids: set[str] = field(default_factory=set)


@dataclass
class ValidationResult:
    outcome: ValidationOutcome
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    policy: Policy | None = None

    @property
    def accepted(self) -> bool:
        return self.outcome != ValidationOutcome.REJECTED


def validate_policy(raw: dict, context: ValidationContext) -> ValidationResult:
    """Validate a raw policy dict/JSON against the schema and runtime context."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        policy = Policy.model_validate(raw)
    except ValidationError as exc:
        return ValidationResult(
            outcome=ValidationOutcome.REJECTED,
            errors=[f"Schema error: {e['loc']}: {e['msg']}" for e in exc.errors()],
        )

    # Unknown camera IDs
    for cam in policy.scope.camera_ids:
        if context.camera_ids and cam not in context.camera_ids:
            errors.append(f"Unknown camera ID: {cam}")

    # Unknown zones
    referenced_zones = set(policy.zones.include) | set(policy.zones.exclude)
    for zone in referenced_zones:
        if context.zone_ids and zone not in context.zone_ids:
            errors.append(f"Unknown zone: {zone}")

    # Metric-distance rules require calibration
    if policy.requires_metric_distance():
        for cam in policy.scope.camera_ids:
            if cam not in context.calibrated_camera_ids:
                warnings.append(
                    f"Distance is measured in image pixels because camera '{cam}' has not "
                    "been calibrated. Collision-risk / proximity alerts will not be enabled "
                    "until calibration is completed."
                )

    # Predicted separation needs a secondary subject
    for cond in policy.conditions.all:
        if cond.type == ConditionType.PREDICTED_SEPARATION and policy.subjects.secondary is None:
            errors.append("predicted_separation requires a secondary subject")
        if cond.type == ConditionType.PROXIMITY and policy.subjects.secondary is None:
            errors.append("proximity requires a secondary subject")

    if errors:
        return ValidationResult(ValidationOutcome.REJECTED, errors=errors, warnings=warnings)
    if warnings:
        return ValidationResult(
            ValidationOutcome.ACCEPTED_WITH_WARNINGS, warnings=warnings, policy=policy
        )
    return ValidationResult(ValidationOutcome.ACCEPTED, policy=policy)
