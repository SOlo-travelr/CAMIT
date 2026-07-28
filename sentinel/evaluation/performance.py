"""Runtime performance metrics: FPS, latency percentiles, real-time factor."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


@dataclass
class PerformanceMeter:
    frame_latencies_s: list[float] = field(default_factory=list)
    frames: int = 0
    dropped: int = 0
    _start: float = field(default_factory=time.perf_counter)

    def record_frame(self, latency_s: float) -> None:
        self.frames += 1
        self.frame_latencies_s.append(latency_s)

    def record_drop(self) -> None:
        self.dropped += 1

    def report(self, video_duration_s: float | None = None) -> dict[str, float]:
        wall = max(1e-9, time.perf_counter() - self._start)
        end_to_end_fps = self.frames / wall
        total = self.frames + self.dropped
        dropped_pct = (self.dropped / total * 100) if total else 0.0
        report = {
            "frames": self.frames,
            "end_to_end_fps": round(end_to_end_fps, 3),
            "avg_latency_ms": round(1000 * (sum(self.frame_latencies_s) / len(self.frame_latencies_s)), 3)
            if self.frame_latencies_s
            else 0.0,
            "p50_latency_ms": round(1000 * _percentile(self.frame_latencies_s, 0.5), 3),
            "p95_latency_ms": round(1000 * _percentile(self.frame_latencies_s, 0.95), 3),
            "p99_latency_ms": round(1000 * _percentile(self.frame_latencies_s, 0.99), 3),
            "dropped_frame_pct": round(dropped_pct, 3),
            "wall_time_s": round(wall, 3),
        }
        if video_duration_s:
            report["real_time_factor"] = round(wall / video_duration_s, 3)
        return report
