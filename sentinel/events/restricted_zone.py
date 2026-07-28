"""Restricted-zone entry event.

State machine per (policy, zone, track):

    OUTSIDE -> PENDING_ENTRY -> INSIDE -> PENDING_EXIT -> OUTSIDE

An entry fires only on a *stable* outside->inside transition, filtered by a
minimum-duration debounce so single-frame boundary jitter never triggers.
"""

from __future__ import annotations

from datetime import datetime

from sentinel.contracts import EventCandidate, TrackObservation
from sentinel.events.geometry import point_in_polygon
from sentinel.events.state import Cooldown, Zone, ZonePhase, ZoneTrackState


class RestrictedZoneRule:
    def __init__(
        self,
        policy_id: str,
        zone: Zone,
        subject_class: str,
        minimum_duration_ms: int,
        cooldown_seconds: float,
        severity: str,
        confidence_threshold: float,
        cooldown: Cooldown,
    ) -> None:
        self.policy_id = policy_id
        self.zone = zone
        self.subject_class = subject_class
        self.minimum_duration_ms = minimum_duration_ms
        self.cooldown_seconds = cooldown_seconds
        self.severity = severity
        self.confidence_threshold = confidence_threshold
        self._cooldown = cooldown
        self._states: dict[int, ZoneTrackState] = {}

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
            st = self._states.setdefault(obs.track_id, ZoneTrackState())
            st.last_seen = now

            if inside:
                if st.phase == ZonePhase.OUTSIDE:
                    st.phase = ZonePhase.PENDING_ENTRY
                    st.pending_since = now
                if st.phase == ZonePhase.PENDING_ENTRY:
                    elapsed_ms = (now - (st.pending_since or now)).total_seconds() * 1000
                    if elapsed_ms >= self.minimum_duration_ms:
                        st.phase = ZonePhase.INSIDE
                        st.inside_since = st.pending_since
                        cand = self._emit(obs, now)
                        if cand:
                            candidates.append(cand)
            else:
                # Left the zone; reset to outside (debounced exit not needed for entry event).
                st.phase = ZonePhase.OUTSIDE
                st.pending_since = None
        return candidates

    def _emit(self, obs: TrackObservation, now: datetime) -> EventCandidate | None:
        key = (self.policy_id, self.zone.zone_id, obs.track_id)
        if not self._cooldown.ready(key, now, self.cooldown_seconds):
            return None
        self._cooldown.mark(key, now)
        return EventCandidate(
            event_type="restricted_zone",
            camera_id=obs.camera_id,
            timestamp=now,
            involved_track_ids=[obs.track_id],
            confidence=obs.confidence,
            severity=self.severity,
            evidence={
                "zone_id": self.zone.zone_id,
                "ground_point_px": obs.ground_point_px,
                "class_name": obs.class_name,
            },
            policy_id=self.policy_id,
        )

    def forget(self, track_id: int) -> None:
        self._states.pop(track_id, None)
