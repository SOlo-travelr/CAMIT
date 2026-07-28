"""Offline benchmark: run the deterministic pipeline over a manifest of videos
and produce reproducible event, tracking, detection and runtime metrics.

Outputs (into ``output_dir``):
    metrics.json, events.csv, false_positives.csv, false_negatives.csv,
    performance.csv, report.html
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from sentinel.config import AppConfig
from sentinel.contracts import BoundingBox
from sentinel.evaluation.detection import evaluate_detections
from sentinel.evaluation.event_metrics import EventInterval, evaluate_events
from sentinel.evaluation.performance import PerformanceMeter
from sentinel.evaluation.tracking import evaluate_tracking
from sentinel.events.engine import EventEngine
from sentinel.events.state import Zone
from sentinel.perception.calibration import compute_homography
from sentinel.perception.detector import SyntheticDetector
from sentinel.perception.observation import ObservationBuilder
from sentinel.perception.tracker import BuiltinTracker
from sentinel.policies.compiler import load_policies_dir
from sentinel.video.source import FileVideoSource


@dataclass
class VideoResult:
    video_id: str
    camera_id: str
    predicted: list[EventInterval] = field(default_factory=list)
    ground_truth: list[EventInterval] = field(default_factory=list)
    duration_s: float = 0.0


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def _intervals_from_candidates(
    candidates: list, cooldown_s: float, nominal_width_s: float = 1.5
) -> list[EventInterval]:
    """Merge event candidates into intervals per (event_type, track set).

    Single-shot events (e.g. zone entry) are padded to ``nominal_width_s`` so
    they have a non-zero temporal extent for IoU matching.
    """
    groups: dict[tuple, list] = {}
    for c in candidates:
        key = (c.camera_id, c.event_type, tuple(sorted(c.involved_track_ids)))
        groups.setdefault(key, []).append(c)
    intervals: list[EventInterval] = []

    def emit(camera_id, event_type, start, end, track_ids) -> None:
        s = _sec(start)
        e = _sec(end)
        if e - s < nominal_width_s:
            e = s + nominal_width_s
        intervals.append(EventInterval(camera_id, event_type, s, e, track_ids))

    for (camera_id, event_type, track_ids), cands in groups.items():
        cands.sort(key=lambda c: c.timestamp)
        start = prev = cands[0].timestamp
        for c in cands[1:]:
            if (c.timestamp - prev).total_seconds() > cooldown_s:
                emit(camera_id, event_type, start, prev, track_ids)
                start = c.timestamp
            prev = c.timestamp
        emit(camera_id, event_type, start, prev, track_ids)
    return intervals


_VIDEO_START = datetime(2026, 1, 1, tzinfo=UTC)


def _sec(ts: datetime) -> float:
    return (ts - _VIDEO_START).total_seconds()


def run_video(video_path: Path, sidecar_path: Path, policies, config: AppConfig) -> tuple:
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    camera_id = sidecar["camera_id"]
    fps = sidecar["fps"]

    zones = {
        zid: Zone(zone_id=zid, polygon=[tuple(p) for p in poly], camera_id=camera_id)
        for zid, poly in sidecar.get("zones", {}).items()
    }

    calibration = None
    calib = sidecar.get("calibration")
    if calib:
        calibration = compute_homography(
            [tuple(p) for p in calib["image_points"]],
            [tuple(p) for p in calib["world_points_m"]],
            camera_id=camera_id,
            resolution=(sidecar["width"], sidecar["height"]),
        )

    # Re-scope policies to this camera for evaluation convenience.
    scoped = []
    for p in policies:
        p2 = p.model_copy(deep=True)
        p2.scope.camera_ids = [camera_id]
        scoped.append(p2)

    detector = SyntheticDetector(sidecar_path, confidence_floor=0.0)
    tracker = BuiltinTracker(
        iou_threshold=config.tracker.iou_threshold,
        max_age_frames=config.tracker.max_age_frames,
        min_hits=config.tracker.min_hits,
    )
    builder = ObservationBuilder()
    engine = EventEngine(
        camera_id=camera_id,
        zones=zones,
        policies=scoped,
        calibration=calibration,
        max_tracking_gap_seconds=config.tracker.max_tracking_gap_seconds,
        min_track_history=config.tracker.min_hits,
    )

    source = FileVideoSource(camera_id, video_path)
    meter = PerformanceMeter()
    all_candidates: list = []
    det_frames: list = []
    track_frames: list = []
    max_frame = 0

    for frame in source.frames():
        t0 = time.perf_counter()
        detections = detector.predict(frame.image, frame)
        tracks = tracker.update(detections, frame)
        observations = builder.build(camera_id, frame.timestamp, tracks, calibration)
        candidates = engine.update(observations, now=frame.timestamp)
        all_candidates.extend(candidates)
        meter.record_frame(time.perf_counter() - t0)
        max_frame = frame.frame_id

        gt_entries = sidecar["frames"].get(str(frame.frame_id), [])
        det_frames.append(
            (detections, [(e["class_name"], BoundingBox(*e["box"])) for e in gt_entries])
        )
        track_frames.append(
            (
                [(t.track_id, t.box) for t in tracks],
                [(e["gt_id"], BoundingBox(*e["box"])) for e in gt_entries if "gt_id" in e],
            )
        )

    duration_s = (max_frame + 1) / fps
    predicted = _intervals_from_candidates(all_candidates, config.event_engine.default_cooldown_seconds)
    ground_truth = [
        EventInterval(
            camera_id,
            e["event_type"],
            float(e["start_s"]),
            float(e["end_s"]),
            tuple(e.get("track_ids", [])),
        )
        for e in sidecar.get("events", [])
    ]
    return predicted, ground_truth, duration_s, meter, det_frames, track_frames, engine.disabled_policies


def run_benchmark(manifest_path: str | Path, config: AppConfig, output_dir: str | Path) -> dict[str, Any]:
    manifest = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8"))
    base = Path(manifest_path).parent
    policies = load_policies_dir(manifest.get("policies_dir", "configs/policies"))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_pred: list[EventInterval] = []
    all_gt: list[EventInterval] = []
    all_det_frames: list = []
    all_track_frames: list = []
    total_hours = 0.0
    perf_rows: list[dict] = []
    disabled: dict[str, str] = {}

    for entry in manifest["videos"]:
        video_path = (base / entry["video"]).resolve()
        sidecar_path = (base / entry["sidecar"]).resolve()
        pred, gt, dur, meter, detf, trkf, dis = run_video(video_path, sidecar_path, policies, config)
        all_pred.extend(pred)
        all_gt.extend(gt)
        all_det_frames.extend(detf)
        all_track_frames.extend(trkf)
        total_hours += dur / 3600.0
        disabled.update(dis)
        perf_rows.append({"video_id": entry["video_id"], **meter.report(dur)})

    event_metrics = evaluate_events(
        all_pred, all_gt, iou_threshold=config.evaluation.temporal_iou_threshold,
        total_camera_hours=max(total_hours, 1e-9),
    )
    detection_metrics = evaluate_detections(all_det_frames)
    tracking_metrics = evaluate_tracking(all_track_frames)

    metrics = {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "config_environment": config.environment,
        "thresholds": {
            "temporal_iou": config.evaluation.temporal_iou_threshold,
            "detector_confidence": config.detector.confidence,
            "tracker": config.tracker.backend,
        },
        "total_camera_hours": round(total_hours, 4),
        "events": {
            k: v for k, v in asdict(event_metrics).items()
            if k not in ("matched", "false_positive_list", "false_negative_list")
        },
        "detection": asdict(detection_metrics),
        "tracking": asdict(tracking_metrics),
        "disabled_policies": disabled,
    }

    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    _write_events_csv(out / "events.csv", all_pred, all_gt)
    _write_interval_csv(out / "false_positives.csv", event_metrics.false_positive_list)
    _write_interval_csv(out / "false_negatives.csv", event_metrics.false_negative_list)
    _write_perf_csv(out / "performance.csv", perf_rows)
    _write_report(out / "report.html", metrics, perf_rows)
    return metrics


# --- writers ---------------------------------------------------------------


def _write_events_csv(path: Path, predicted, ground_truth) -> None:
    lines = ["kind,camera_id,event_type,start_s,end_s,track_ids"]
    for p in predicted:
        lines.append(f"predicted,{p.camera_id},{p.event_type},{p.start_s:.3f},{p.end_s:.3f},{'|'.join(map(str, p.track_ids))}")
    for g in ground_truth:
        lines.append(f"ground_truth,{g.camera_id},{g.event_type},{g.start_s:.3f},{g.end_s:.3f},{'|'.join(map(str, g.track_ids))}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_interval_csv(path: Path, intervals) -> None:
    lines = ["camera_id,event_type,start_s,end_s,track_ids"]
    for i in intervals:
        lines.append(f"{i.camera_id},{i.event_type},{i.start_s:.3f},{i.end_s:.3f},{'|'.join(map(str, i.track_ids))}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_perf_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for r in rows:
        lines.append(",".join(str(r.get(h, "")) for h in headers))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(path: Path, metrics: dict, perf_rows: list[dict]) -> None:
    ev = metrics["events"]
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Sentinel Benchmark Report</title>
<style>body{{font-family:system-ui,Arial;margin:2rem;max-width:960px}}
table{{border-collapse:collapse;margin:1rem 0}}td,th{{border:1px solid #ccc;padding:6px 10px}}
.kpi{{display:inline-block;margin:0.5rem 1rem 0.5rem 0;padding:0.5rem 1rem;background:#f4f4f8;border-radius:8px}}
code{{background:#eee;padding:1px 4px}}</style></head><body>
<h1>Sentinel Benchmark Report</h1>
<p>Generated {metrics['generated_at']} · commit <code>{metrics.get('git_commit')}</code> ·
env <code>{metrics['config_environment']}</code></p>
<h2>Event metrics (temporal IoU >= {metrics['thresholds']['temporal_iou']})</h2>
<div class="kpi">Precision <b>{ev['precision']}</b></div>
<div class="kpi">Recall <b>{ev['recall']}</b></div>
<div class="kpi">F1 <b>{ev['f1']}</b></div>
<div class="kpi">False alerts / camera-day <b>{ev['false_alerts_per_camera_day']}</b></div>
<div class="kpi">P95 detection delay <b>{ev['p95_detection_delay_s']} s</b></div>
<div class="kpi">Duplicates <b>{ev['duplicate_alerts']}</b></div>
<h2>Detection (overall)</h2>
<p>{metrics['detection']['overall']}</p>
<h2>Tracking</h2>
<p>MOTA {metrics['tracking']['mota']} · ID switches {metrics['tracking']['id_switches']} ·
mostly-tracked {metrics['tracking']['mostly_tracked']}</p>
<h2>Runtime</h2>
<table><tr>{''.join(f'<th>{h}</th>' for h in (perf_rows[0].keys() if perf_rows else []))}</tr>
{''.join('<tr>' + ''.join(f'<td>{v}</td>' for v in r.values()) + '</tr>' for r in perf_rows)}</table>
<h2>Disabled policies</h2>
<pre>{json.dumps(metrics['disabled_policies'], indent=2)}</pre>
</body></html>"""
    path.write_text(html, encoding="utf-8")
