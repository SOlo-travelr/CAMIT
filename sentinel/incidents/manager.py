"""Incident manager: deduplicates event candidates into incidents.

Deduplication key = camera_id + event_type + sorted(track_ids) + cooldown window.
Related candidates within the window extend an existing incident instead of
creating a new one.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sentinel.contracts import EventCandidate, Incident, IncidentEvidence
from sentinel.incidents.explanation import explain


class IncidentManager:
    def __init__(self, cooldown_window_seconds: int = 30) -> None:
        self.cooldown_window_seconds = cooldown_window_seconds
        self._open: dict[tuple, Incident] = {}

    def _key(self, c: EventCandidate) -> tuple:
        return (c.camera_id, c.event_type, tuple(sorted(c.involved_track_ids)))

    def ingest(self, candidate: EventCandidate) -> Incident | None:
        """Return a *new* Incident, or None if merged into an existing one."""
        key = self._key(candidate)
        existing = self._open.get(key)
        summary, conditions = explain(candidate)

        if existing is not None:
            within = candidate.timestamp - existing.end_time <= timedelta(
                seconds=self.cooldown_window_seconds
            )
            if within:
                existing.end_time = candidate.timestamp
                existing.confidence = max(existing.confidence, candidate.confidence)
                existing.evidence.observations.update(candidate.evidence)
                return None

        incident = Incident(
            incident_id=str(uuid.uuid4()),
            event_type=candidate.event_type,
            camera_id=candidate.camera_id,
            start_time=candidate.timestamp,
            end_time=candidate.timestamp,
            severity=candidate.severity,
            confidence=candidate.confidence,
            track_ids=list(candidate.involved_track_ids),
            policy_id=candidate.policy_id,
            evidence=IncidentEvidence(
                observations={"summary": summary, **candidate.evidence},
                triggered_conditions=conditions,
            ),
        )
        self._open[key] = incident
        return incident

    def flush_expired(self, now: datetime) -> list[Incident]:
        """Close and return incidents whose cooldown window has elapsed."""
        expired = []
        for key, inc in list(self._open.items()):
            if now - inc.end_time > timedelta(seconds=self.cooldown_window_seconds):
                expired.append(inc)
                del self._open[key]
        return expired
