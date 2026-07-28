"""Loitering event.

Tracks continuous dwell time inside a zone per (policy, zone, track). Tolerates
brief tracking gaps up to ``max_tracking_gap_seconds`` without resetting the
timer; a longer gap or a zone exit resets it. Fires once per dwell episode
(subject to cooldown).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sentinel.contracts import EventCandidate, TrackObservation
from sentinel.events.geometry import point_in_polygon
from sentinel.events.state import Cooldown, Zone


@dataclass
class _DwellState:
    entry_time: datetime | None = None
    last_inside: datetime | None = None
    fired: bool = False


class LoiteringRule:
    def __init__(
        self,
        policy_id: str,
        zone: Zone,
        subject_class: str,
        minimum_seconds: float,
        max_tracking_gap_seconds: float,
        cooldown_seconds: float,
        severity: str,
        confidence_threshold: float,
        cooldown: Cooldown,
    ) -> None:
        self.policy_id = policy_id
        self.zone = zone
        self.subject_class = subject_class
        self.minimum_seconds = minimum_seconds
        self.max_tracking_gap_seconds = max_tracking_gap_seconds
        self.cooldown_seconds = cooldown_seconds
        self.severity = severity
        self.confidence_threshold = confidence_threshold
        self._cooldown = cooldown
        self._states: dict[int, _DwellState] = {}

    def update(
        self, observations: list[TrackObservation], now: datetime
    ) -> list[EventCandidate]:
        candidates: list[EventCandidate] = []
        for obs in observations:
            if obs.class_name != self.subject_class:
                continue
            if obs.confidence < self.confidence_threshold:
                continue
            inside = point_in_polygon(obs.ground_point_px, self.zone.polygon)
            st = self._states.setdefault(obs.track_id, _DwellState())

            if not inside:
                self._states[obs.track_id] = _DwellState()
                continue

            if st.entry_time is None:
                st.entry_time = now
            elif st.last_inside is not None:
                gap = (now - st.last_inside).total_seconds()
                if gap > self.max_tracking_gap_seconds:
                    # Gap too long: restart the dwell timer.
                    st.entry_time = now
                    st.fired = False
            st.last_inside = now

            dwell = (now - st.entry_time).total_seconds()
            if dwell >= self.minimum_seconds and not st.fired:
                cand = self._emit(obs, now, dwell)
                if cand:
                    st.fired = True
                    candidates.append(cand)
        return candidates

    def _emit(
        self, obs: TrackObservation, now: datetime, dwell: float
    ) -> EventCandidate | None:
        key = (self.policy_id, self.zone.zone_id, obs.track_id)
        if not self._cooldown.ready(key, now, self.cooldown_seconds):
            return None
        self._cooldown.mark(key, now)
        return EventCandidate(
            event_type="loitering",
            camera_id=obs.camera_id,
            timestamp=now,
            involved_track_ids=[obs.track_id],
            confidence=obs.confidence,
            severity=self.severity,
            evidence={
                "zone_id": self.zone.zone_id,
                "dwell_seconds": round(dwell, 3),
                "minimum_seconds": self.minimum_seconds,
            },
            policy_id=self.policy_id,
        )

    def forget(self, track_id: int) -> None:
        self._states.pop(track_id, None)
