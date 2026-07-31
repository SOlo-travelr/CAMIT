"""Pedestrian-vehicle proximity event (requires metric calibration).

Fires when a person and a moving vehicle stay within a metric distance threshold
for several consecutive updates. Uses ground-plane metric coordinates only; if a
camera is uncalibrated this rule is disabled at compile time.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sentinel.contracts import EventCandidate, TrackObservation
from sentinel.events.geometry import euclidean
from sentinel.events.state import Cooldown


class ProximityRule:
    def __init__(
        self,
        policy_id: str,
        primary_class: str,
        secondary_class: str,
        threshold_meters: float,
        minimum_vehicle_speed_mps: float,
        min_consecutive_updates: int,
        min_track_history: int,
        cooldown_seconds: float,
        severity: str,
        confidence_threshold: float,
        cooldown: Cooldown,
    ) -> None:
        self.policy_id = policy_id
        self.primary_class = primary_class
        self.secondary_class = secondary_class
        self.threshold_meters = threshold_meters
        self.minimum_vehicle_speed_mps = minimum_vehicle_speed_mps
        self.min_consecutive_updates = min_consecutive_updates
        self.min_track_history = min_track_history
        self.cooldown_seconds = cooldown_seconds
        self.severity = severity
        self.confidence_threshold = confidence_threshold
        self._cooldown = cooldown
        self._streak: dict[tuple[int, int], int] = defaultdict(int)
        self._history: dict[int, int] = defaultdict(int)

    def update(
        self, observations: list[TrackObservation], now: datetime
    ) -> list[EventCandidate]:
        people = [o for o in observations if o.class_name == self.primary_class]
        vehicles = [o for o in observations if o.class_name == self.secondary_class]
        for o in observations:
            self._history[o.track_id] += 1

        candidates: list[EventCandidate] = []
        seen_pairs: set[tuple[int, int]] = set()

        for person in people:
            if person.ground_point_m is None or person.confidence < self.confidence_threshold:
                continue
            for veh in vehicles:
                if veh.ground_point_m is None or veh.confidence < self.confidence_threshold:
                    continue
                pair = (person.track_id, veh.track_id)
                seen_pairs.add(pair)

                if (
                    self._history[person.track_id] < self.min_track_history
                    or self._history[veh.track_id] < self.min_track_history
                ):
                    continue

                veh_speed = (
                    euclidean(veh.velocity_mps, (0.0, 0.0)) if veh.velocity_mps else 0.0
                )
                dist = euclidean(person.ground_point_m, veh.ground_point_m)

                if dist <= self.threshold_meters and veh_speed >= self.minimum_vehicle_speed_mps:
                    self._streak[pair] += 1
                else:
                    self._streak[pair] = 0

                if self._streak[pair] >= self.min_consecutive_updates:
                    cand = self._emit(person, veh, now, dist, veh_speed)
                    if cand:
                        candidates.append(cand)

        # Decay streaks for pairs not seen this update.
        for pair in list(self._streak):
            if pair not in seen_pairs:
                self._streak[pair] = 0
        return candidates

    def forget(self, track_id: int) -> None:
        self._history.pop(track_id, None)
        for pair in [p for p in self._streak if track_id in p]:
            self._streak.pop(pair, None)

    def _emit(self, person, veh, now, dist, veh_speed) -> EventCandidate | None:
        key = (self.policy_id, person.track_id, veh.track_id)
        if not self._cooldown.ready(key, now, self.cooldown_seconds):
            return None
        self._cooldown.mark(key, now)
        confidence = min(person.confidence, veh.confidence)
        return EventCandidate(
            event_type="proximity",
            camera_id=person.camera_id,
            timestamp=now,
            involved_track_ids=[person.track_id, veh.track_id],
            confidence=confidence,
            severity=self.severity,
            evidence={
                "person_track_id": person.track_id,
                "vehicle_track_id": veh.track_id,
                "current_distance_m": round(dist, 3),
                "relative_speed_mps": round(veh_speed, 3),
                "threshold_meters": self.threshold_meters,
            },
            policy_id=self.policy_id,
        )
