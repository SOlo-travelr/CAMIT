"""Human-readable explanations of why an incident fired.

Deterministic, template-based text derived from the structured evidence. An LLM
may later paraphrase these summaries, but the facts always come from the engine.
"""

from __future__ import annotations

from sentinel.contracts import EventCandidate


def explain(candidate: EventCandidate) -> tuple[str, list[str]]:
    """Return (summary, triggered_conditions) for an event candidate."""
    ev = candidate.evidence
    etype = candidate.event_type
    if etype == "restricted_zone":
        summary = (
            f"Person (track {candidate.involved_track_ids[0]}) entered restricted zone "
            f"'{ev.get('zone_id')}'."
        )
        return summary, [f"ground_point inside zone '{ev.get('zone_id')}'"]
    if etype == "loitering":
        summary = (
            f"Track {candidate.involved_track_ids[0]} loitered in zone "
            f"'{ev.get('zone_id')}' for {ev.get('dwell_seconds')}s "
            f"(threshold {ev.get('minimum_seconds')}s)."
        )
        return summary, [f"dwell_seconds >= {ev.get('minimum_seconds')}"]
    if etype == "proximity":
        summary = (
            f"Person {ev.get('person_track_id')} within {ev.get('current_distance_m')} m of "
            f"moving vehicle {ev.get('vehicle_track_id')}."
        )
        return summary, [f"current_distance_m <= {ev.get('threshold_meters')}"]
    if etype == "collision_risk":
        summary = (
            f"Predicted near-miss between person {ev.get('person_track_id')} and vehicle "
            f"{ev.get('vehicle_track_id')}: predicted minimum distance "
            f"{ev.get('predicted_minimum_distance_m')} m in "
            f"{ev.get('time_to_minimum_distance_s')} s."
        )
        return summary, [
            f"predicted_minimum_distance_m < {ev.get('predicted_minimum_distance_m')}",
            f"time_to_minimum_distance_s < {ev.get('time_to_minimum_distance_s')}",
        ]
    return f"Event {etype} on camera {candidate.camera_id}.", []
