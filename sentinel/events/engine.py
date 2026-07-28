"""The stateful, deterministic event engine (one instance per camera).

Compiles validated policies into concrete rule objects and evaluates them each
update against the current :class:`TrackObservation` list. Returns
:class:`EventCandidate` objects; incident creation / dedup happens downstream.
"""

from __future__ import annotations

from datetime import datetime

from sentinel.contracts import EventCandidate, TrackObservation
from sentinel.events.collision_risk import CollisionRiskRule
from sentinel.events.loitering import LoiteringRule
from sentinel.events.proximity import ProximityRule
from sentinel.events.restricted_zone import RestrictedZoneRule
from sentinel.events.state import Cooldown, Zone
from sentinel.perception.calibration import CameraCalibration
from sentinel.policies.models import ConditionType, Policy


class EventEngine:
    def __init__(
        self,
        camera_id: str,
        zones: dict[str, Zone],
        policies: list[Policy],
        calibration: CameraCalibration | None = None,
        max_tracking_gap_seconds: float = 1.5,
        min_track_history: int = 3,
    ) -> None:
        self.camera_id = camera_id
        self.zones = zones
        self.calibration = calibration
        self.max_tracking_gap_seconds = max_tracking_gap_seconds
        self.min_track_history = min_track_history
        self._cooldown = Cooldown()
        self._rules: list = []
        self.disabled_policies: dict[str, str] = {}
        for policy in policies:
            if policy.enabled and camera_id in policy.scope.camera_ids:
                self._compile(policy)

    # -- compilation --------------------------------------------------------
    def _condition(self, policy: Policy, ctype: ConditionType):
        for c in policy.conditions.all:
            if c.type == ctype:
                return c
        return None

    def _zone_for(self, policy: Policy) -> Zone | None:
        for zid in policy.zones.include:
            if zid in self.zones:
                return self.zones[zid]
        return None

    def _compile(self, policy: Policy) -> None:
        etype = policy.event.type.value
        metric_ready = self.calibration is not None and self.calibration.is_metric

        if policy.requires_metric_distance() and not metric_ready:
            self.disabled_policies[policy.policy_id] = (
                "metric distance rule disabled: camera not calibrated"
            )
            return

        if etype == "restricted_zone":
            zone = self._zone_for(policy)
            if zone is None:
                self.disabled_policies[policy.policy_id] = "no matching zone"
                return
            self._rules.append(
                RestrictedZoneRule(
                    policy_id=policy.policy_id,
                    zone=zone,
                    subject_class=policy.subjects.primary.class_,
                    minimum_duration_ms=policy.event.minimum_duration_ms,
                    cooldown_seconds=policy.event.cooldown_seconds,
                    severity=policy.event.severity.value,
                    confidence_threshold=policy.event.confidence_threshold,
                    cooldown=self._cooldown,
                )
            )
        elif etype == "loitering":
            zone = self._zone_for(policy)
            dwell = self._condition(policy, ConditionType.DWELL_TIME)
            if zone is None or dwell is None:
                self.disabled_policies[policy.policy_id] = "loitering needs zone + dwell_time"
                return
            self._rules.append(
                LoiteringRule(
                    policy_id=policy.policy_id,
                    zone=zone,
                    subject_class=policy.subjects.primary.class_,
                    minimum_seconds=dwell.minimum_seconds or 0.0,
                    max_tracking_gap_seconds=self.max_tracking_gap_seconds,
                    cooldown_seconds=policy.event.cooldown_seconds,
                    severity=policy.event.severity.value,
                    confidence_threshold=policy.event.confidence_threshold,
                    cooldown=self._cooldown,
                )
            )
        elif etype == "proximity":
            prox = self._condition(policy, ConditionType.PROXIMITY)
            motion = self._condition(policy, ConditionType.OBJECT_MOTION)
            if policy.subjects.secondary is None or prox is None:
                self.disabled_policies[policy.policy_id] = "proximity needs secondary + proximity"
                return
            self._rules.append(
                ProximityRule(
                    policy_id=policy.policy_id,
                    primary_class=policy.subjects.primary.class_,
                    secondary_class=policy.subjects.secondary.class_,
                    threshold_meters=prox.threshold_meters or 1.0,
                    minimum_vehicle_speed_mps=(motion.minimum_speed_mps if motion else 0.3),
                    min_consecutive_updates=3,
                    min_track_history=self.min_track_history,
                    cooldown_seconds=policy.event.cooldown_seconds,
                    severity=policy.event.severity.value,
                    confidence_threshold=policy.event.confidence_threshold,
                    cooldown=self._cooldown,
                )
            )
        elif etype == "collision_risk":
            sep = self._condition(policy, ConditionType.PREDICTED_SEPARATION)
            motion = self._condition(policy, ConditionType.OBJECT_MOTION)
            if policy.subjects.secondary is None or sep is None:
                self.disabled_policies[policy.policy_id] = (
                    "collision_risk needs secondary + predicted_separation"
                )
                return
            self._rules.append(
                CollisionRiskRule(
                    policy_id=policy.policy_id,
                    primary_class=policy.subjects.primary.class_,
                    secondary_class=policy.subjects.secondary.class_,
                    horizon_seconds=sep.horizon_seconds or 3.0,
                    threshold_meters=sep.threshold_meters or 1.0,
                    minimum_vehicle_speed_mps=(motion.minimum_speed_mps if motion else 0.5),
                    min_track_history=self.min_track_history,
                    cooldown_seconds=policy.event.cooldown_seconds,
                    severity=policy.event.severity.value,
                    confidence_threshold=policy.event.confidence_threshold,
                    cooldown=self._cooldown,
                )
            )
        else:  # pragma: no cover - guarded by schema
            self.disabled_policies[policy.policy_id] = f"unsupported event type {etype}"

    # -- evaluation ---------------------------------------------------------
    def update(
        self, observations: list[TrackObservation], now: datetime | None = None
    ) -> list[EventCandidate]:
        if now is None:
            now = observations[0].timestamp if observations else datetime.now()
        candidates: list[EventCandidate] = []
        for rule in self._rules:
            candidates.extend(rule.update(observations, now))
        return candidates

    @property
    def active_rule_count(self) -> int:
        return len(self._rules)
