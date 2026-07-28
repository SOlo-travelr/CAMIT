"""Predicted pedestrian-vehicle collision-risk event.

Uses a constant-velocity trajectory-projection model over a configurable horizon
to estimate time-to-closest-approach and predicted minimum separation in metric
ground coordinates. Requires calibration. Risk is initially rule-based; a
calibrated logistic score can replace the boolean rule later without changing
this interface.
"""

from __future__ import annotations

from datetime import datetime

from sentinel.contracts import EventCandidate, TrackObservation
from sentinel.events.geometry import closest_approach, euclidean
from sentinel.events.state import Cooldown


def rule_based_risk(
    predicted_min_distance_m: float,
    time_to_closest_s: float,
    vehicle_speed_mps: float,
    distance_threshold_m: float = 1.0,
    time_threshold_s: float = 2.0,
    min_vehicle_speed_mps: float = 0.5,
) -> bool:
    return (
        predicted_min_distance_m < distance_threshold_m
        and time_to_closest_s < time_threshold_s
        and vehicle_speed_mps > min_vehicle_speed_mps
    )


class CollisionRiskRule:
    def __init__(
        self,
        policy_id: str,
        primary_class: str,
        secondary_class: str,
        horizon_seconds: float,
        threshold_meters: float,
        minimum_vehicle_speed_mps: float,
        min_track_history: int,
        cooldown_seconds: float,
        severity: str,
        confidence_threshold: float,
        cooldown: Cooldown,
        time_threshold_s: float = 2.0,
    ) -> None:
        self.policy_id = policy_id
        self.primary_class = primary_class
        self.secondary_class = secondary_class
        self.horizon_seconds = horizon_seconds
        self.threshold_meters = threshold_meters
        self.minimum_vehicle_speed_mps = minimum_vehicle_speed_mps
        self.min_track_history = min_track_history
        self.cooldown_seconds = cooldown_seconds
        self.severity = severity
        self.confidence_threshold = confidence_threshold
        self.time_threshold_s = time_threshold_s
        self._cooldown = cooldown
        self._history: dict[int, int] = {}

    def update(
        self, observations: list[TrackObservation], now: datetime
    ) -> list[EventCandidate]:
        for o in observations:
            self._history[o.track_id] = self._history.get(o.track_id, 0) + 1

        people = [o for o in observations if o.class_name == self.primary_class]
        vehicles = [o for o in observations if o.class_name == self.secondary_class]
        candidates: list[EventCandidate] = []

        for person in people:
            if person.ground_point_m is None or person.velocity_mps is None:
                continue
            if person.confidence < self.confidence_threshold:
                continue
            for veh in vehicles:
                if veh.ground_point_m is None or veh.velocity_mps is None:
                    continue
                if veh.confidence < self.confidence_threshold:
                    continue
                if (
                    self._history.get(person.track_id, 0) < self.min_track_history
                    or self._history.get(veh.track_id, 0) < self.min_track_history
                ):
                    continue

                ca = closest_approach(
                    person.ground_point_m,
                    person.velocity_mps,
                    veh.ground_point_m,
                    veh.velocity_mps,
                    horizon_s=self.horizon_seconds,
                )
                veh_speed = euclidean(veh.velocity_mps, (0.0, 0.0))

                triggered = (
                    ca.min_distance < self.threshold_meters
                    and ca.time_to_closest_s < self.time_threshold_s
                    and veh_speed > self.minimum_vehicle_speed_mps
                )
                if triggered:
                    cand = self._emit(person, veh, now, ca, veh_speed)
                    if cand:
                        candidates.append(cand)
        return candidates

    def _emit(self, person, veh, now, ca, veh_speed) -> EventCandidate | None:
        key = (self.policy_id, person.track_id, veh.track_id)
        if not self._cooldown.ready(key, now, self.cooldown_seconds):
            return None
        self._cooldown.mark(key, now)
        confidence = min(person.confidence, veh.confidence)
        return EventCandidate(
            event_type="collision_risk",
            camera_id=person.camera_id,
            timestamp=now,
            involved_track_ids=[person.track_id, veh.track_id],
            confidence=confidence,
            severity=self.severity,
            evidence={
                "person_track_id": person.track_id,
                "vehicle_track_id": veh.track_id,
                "current_distance_m": round(ca.current_distance, 3),
                "predicted_minimum_distance_m": round(ca.min_distance, 3),
                "time_to_minimum_distance_s": round(ca.time_to_closest_s, 3),
                "relative_speed_mps": round(ca.relative_speed, 3),
                "vehicle_speed_mps": round(veh_speed, 3),
            },
            policy_id=self.policy_id,
        )
