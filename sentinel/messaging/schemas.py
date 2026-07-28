"""Message payload schemas exchanged over the bus."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sentinel.contracts import EventCandidate


def event_candidate_to_message(candidate: EventCandidate) -> dict[str, Any]:
    payload = asdict(candidate)
    payload["timestamp"] = candidate.timestamp.isoformat()
    return payload
