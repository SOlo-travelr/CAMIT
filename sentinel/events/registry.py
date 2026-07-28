"""Registry mapping event types to their rule builders."""

from __future__ import annotations

from sentinel.contracts import EventType

SUPPORTED_EVENT_TYPES = {e.value for e in EventType}

# Which condition types are required for each event type.
EVENT_CONDITION_HINTS = {
    EventType.RESTRICTED_ZONE.value: ["zone_entry"],
    EventType.LOITERING.value: ["dwell_time"],
    EventType.PROXIMITY.value: ["proximity"],
    EventType.COLLISION_RISK.value: ["predicted_separation"],
}


def is_supported_event(event_type: str) -> bool:
    return event_type in SUPPORTED_EVENT_TYPES
