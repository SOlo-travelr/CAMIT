"""Pydantic models defining the restricted policy schema.

Natural language compiles into these validated structures; nothing else is ever
executed. The LLM may only *select* from the enumerated conditions and event
types below.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from sentinel.contracts import EventType, Severity

SUPPORTED_CLASSES = {"person", "forklift", "car", "truck", "vehicle"}
DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


class ConditionType(str, Enum):
    ZONE_ENTRY = "zone_entry"
    DWELL_TIME = "dwell_time"
    OBJECT_MOTION = "object_motion"
    PROXIMITY = "proximity"
    PREDICTED_SEPARATION = "predicted_separation"


class Schedule(BaseModel):
    timezone: str = "UTC"
    days: list[str] = Field(default_factory=lambda: list(DAYS))
    start: str = "00:00"
    end: str = "23:59"

    @field_validator("days")
    @classmethod
    def _valid_days(cls, v: list[str]) -> list[str]:
        bad = [d for d in v if d not in DAYS]
        if bad:
            raise ValueError(f"Invalid day(s): {bad}")
        return v

    @field_validator("start", "end")
    @classmethod
    def _valid_time(cls, v: str) -> str:
        hh, _, mm = v.partition(":")
        if not (hh.isdigit() and mm.isdigit() and 0 <= int(hh) < 24 and 0 <= int(mm) < 60):
            raise ValueError(f"Invalid time: {v}")
        return v


class Scope(BaseModel):
    camera_ids: list[str]
    schedule: Schedule = Field(default_factory=Schedule)


class SubjectSpec(BaseModel):
    class_: str = Field(alias="class")

    model_config = {"populate_by_name": True}

    @field_validator("class_")
    @classmethod
    def _supported(cls, v: str) -> str:
        if v not in SUPPORTED_CLASSES:
            raise ValueError(f"Unsupported class '{v}'. Allowed: {sorted(SUPPORTED_CLASSES)}")
        return v


class Subjects(BaseModel):
    primary: SubjectSpec
    secondary: SubjectSpec | None = None


class Zones(BaseModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class Condition(BaseModel):
    type: ConditionType
    subject: str | None = None
    subjects: list[str] | None = None
    minimum_seconds: float | None = None
    minimum_speed_mps: float | None = None
    horizon_seconds: float | None = None
    threshold_meters: float | None = None

    @field_validator("minimum_seconds", "minimum_speed_mps", "horizon_seconds", "threshold_meters")
    @classmethod
    def _non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Durations, speeds and distances must be non-negative")
        return v


class Conditions(BaseModel):
    all: list[Condition] = Field(default_factory=list)


class EventSpec(BaseModel):
    type: EventType
    cooldown_seconds: int = 30
    minimum_duration_ms: int = 0
    severity: Severity = Severity.MEDIUM
    confidence_threshold: float = 0.4

    @field_validator("cooldown_seconds", "minimum_duration_ms")
    @classmethod
    def _non_negative_int(cls, v: int) -> int:
        if v < 0:
            raise ValueError("cooldown and duration must be non-negative")
        return v

    @field_validator("confidence_threshold")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence_threshold must be in [0, 1]")
        return v


class Evidence(BaseModel):
    pre_event_seconds: float = 8.0
    post_event_seconds: float = 8.0
    save_clip: bool = True
    save_snapshot: bool = True


class Review(BaseModel):
    human_confirmation_required: bool = True


class Policy(BaseModel):
    policy_id: str
    name: str
    enabled: bool = True
    scope: Scope
    subjects: Subjects
    zones: Zones = Field(default_factory=Zones)
    conditions: Conditions
    event: EventSpec
    evidence: Evidence = Field(default_factory=Evidence)
    review: Review = Field(default_factory=Review)

    def requires_metric_distance(self) -> bool:
        return any(
            c.type in (ConditionType.PROXIMITY, ConditionType.PREDICTED_SEPARATION)
            for c in self.conditions.all
        )
