"""Prometheus-compatible metrics with a no-op fallback.

The core pipeline must run without the ``prometheus_client`` dependency, so we
provide lightweight shims that record nothing when the library is absent.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - exercised only when prometheus is installed
    from prometheus_client import Counter, Gauge, Histogram, generate_latest

    _PROM_AVAILABLE = True
except Exception:  # pragma: no cover
    _PROM_AVAILABLE = False

    class _Noop:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def labels(self, *_: Any, **__: Any) -> _Noop:
            return self

        def inc(self, *_: Any, **__: Any) -> None:
            pass

        def observe(self, *_: Any, **__: Any) -> None:
            pass

        def set(self, *_: Any, **__: Any) -> None:
            pass

    Counter = Gauge = Histogram = _Noop  # type: ignore[assignment,misc]

    def generate_latest() -> bytes:  # type: ignore[misc]
        return b""


FRAMES_PROCESSED = Counter(
    "sentinel_frames_processed_total", "Frames processed", ["camera_id"]
)
FRAMES_DROPPED = Counter(
    "sentinel_frames_dropped_total", "Frames dropped", ["camera_id"]
)
DETECTIONS = Counter(
    "sentinel_detections_total", "Detections emitted", ["camera_id", "class_name"]
)
EVENTS_EMITTED = Counter(
    "sentinel_events_total", "Event candidates emitted", ["camera_id", "event_type"]
)
INCIDENTS_CREATED = Counter(
    "sentinel_incidents_total", "Incidents created", ["camera_id", "event_type"]
)
PIPELINE_LATENCY = Histogram(
    "sentinel_pipeline_latency_seconds", "Frame-to-event latency", ["camera_id"]
)
CAMERA_UP = Gauge("sentinel_camera_up", "Camera health (1 up / 0 down)", ["camera_id"])


def metrics_available() -> bool:
    return _PROM_AVAILABLE


def render_metrics() -> bytes:
    return generate_latest()
