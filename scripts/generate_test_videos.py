"""Generate deterministic synthetic warehouse videos with ground truth.

Because the scenes are procedurally generated, the ground truth (detection
boxes, track ids, and event intervals) is known exactly. This is more useful for
validating event logic than a random downloaded clip, and it runs anywhere with
no GPU. A real MP4 downloader is provided separately in ``import_video.py``.

Each scenario writes:
    <name>.mp4         encoded frames
    <name>.gt.json     detector sidecar + zones + calibration + event ground truth
and an aggregate manifest at datasets/manifests/eval.yaml.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT, FPS = 1280, 720, 15
PX_PER_M = 50.0
CAMERA_ID = "warehouse_cam_03"

# Ground-plane homography correspondences (image corners -> metres).
CALIBRATION = {
    "image_points": [[0, 720], [1280, 720], [1280, 0], [0, 0]],
    "world_points_m": [[0.0, 0.0], [25.6, 0.0], [25.6, 14.4], [0.0, 14.4]],
}
FORKLIFT_LANE = [[500, 300], [900, 300], [900, 720], [500, 720]]

_COLORS = {"person": (0, 200, 0), "forklift": (0, 140, 255)}
_SIZE = {"person": (40, 90), "forklift": (80, 70)}


def metric_to_ground_px(x_m: float, y_m: float) -> tuple[float, float]:
    return (x_m * PX_PER_M, HEIGHT - y_m * PX_PER_M)


@dataclass
class MovingObject:
    gt_id: int
    class_name: str
    position_m: Callable[[float], tuple[float, float]]

    def box_at(self, t: float) -> tuple[float, float, float, float]:
        x_m, y_m = self.position_m(t)
        gx, gy = metric_to_ground_px(x_m, y_m)
        w, h = _SIZE[self.class_name]
        x1, x2 = gx - w / 2, gx + w / 2
        y2 = gy
        y1 = gy - h
        return (x1, y1, x2, y2)


@dataclass
class Scenario:
    name: str
    duration_s: float
    objects: list[MovingObject]
    zones: dict[str, list[list[int]]] = field(default_factory=dict)
    calibration: dict | None = None
    events: list[dict] = field(default_factory=list)


def _restricted_entry() -> Scenario:
    def person(t: float) -> tuple[float, float]:
        # Walks in from the left, enters the lane (x>=10 m) around t=1.3 s, stops.
        x = 8.0 + 1.5 * t if t < 2.0 else 11.0
        return (x, 5.0)

    return Scenario(
        name="restricted_entry",
        duration_s=9.0,
        objects=[MovingObject(1, "person", person)],
        zones={"forklift_lane": FORKLIFT_LANE},
        calibration=CALIBRATION,
        events=[
            {"event_type": "restricted_zone", "start_s": 1.0, "end_s": 3.0, "track_ids": [1]},
            {"event_type": "loitering", "start_s": 6.0, "end_s": 8.9, "track_ids": [1]},
        ],
    )


def _near_miss() -> Scenario:
    def person(t: float) -> tuple[float, float]:
        return (5.0 + 1.0 * t, 5.0)  # 1 m/s, stays outside the lane

    def forklift(t: float) -> tuple[float, float]:
        return (15.0 - 2.0 * t, 5.6)  # 2 m/s toward the person, 0.6 m lateral offset

    return Scenario(
        name="near_miss",
        duration_s=6.0,
        objects=[MovingObject(1, "person", person), MovingObject(2, "forklift", forklift)],
        zones={},  # no zone -> only collision_risk is evaluated here
        calibration=CALIBRATION,
        events=[{"event_type": "collision_risk", "start_s": 2.0, "end_s": 4.5, "track_ids": [1, 2]}],
    )


def _parallel_negative() -> Scenario:
    def person(t: float) -> tuple[float, float]:
        return (5.0 + 1.0 * t, 3.0)

    def forklift(t: float) -> tuple[float, float]:
        return (5.0 + 1.0 * t, 11.0)  # 8 m away, parallel course -> no risk

    return Scenario(
        name="parallel_negative",
        duration_s=6.0,
        objects=[MovingObject(1, "person", person), MovingObject(2, "forklift", forklift)],
        zones={},
        calibration=CALIBRATION,
        events=[],  # hard negative: nothing should fire
    )


SCENARIOS = [_restricted_entry, _near_miss, _parallel_negative]


def render_scenario(scenario: Scenario, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    video_path = out_dir / f"{scenario.name}.mp4"
    sidecar_path = out_dir / f"{scenario.name}.gt.json"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, FPS, (WIDTH, HEIGHT))
    n_frames = int(scenario.duration_s * FPS)
    frames: dict[str, list[dict]] = {}

    try:
        for frame_id in range(n_frames):
            t = frame_id / FPS
            canvas = np.full((HEIGHT, WIDTH, 3), 40, dtype=np.uint8)
            for _zid, poly in scenario.zones.items():
                pts = np.array(poly, dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(canvas, [pts], True, (0, 0, 200), 2)
            entries: list[dict] = []
            for obj in scenario.objects:
                x1, y1, x2, y2 = obj.box_at(t)
                cv2.rectangle(
                    canvas,
                    (int(x1), int(y1)),
                    (int(x2), int(y2)),
                    _COLORS[obj.class_name],
                    -1,
                )
                entries.append(
                    {
                        "class_name": obj.class_name,
                        "box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                        "confidence": 0.95,
                        "gt_id": obj.gt_id,
                    }
                )
            frames[str(frame_id)] = entries
            writer.write(canvas)
    finally:
        writer.release()

    sidecar = {
        "camera_id": CAMERA_ID,
        "fps": FPS,
        "width": WIDTH,
        "height": HEIGHT,
        "zones": scenario.zones,
        "calibration": scenario.calibration,
        "frames": frames,
        "events": scenario.events,
    }
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    return video_path, sidecar_path


def write_manifest(entries: list[tuple[str, Path, Path]], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_dir = manifest_path.parent
    videos = []
    for name, video_path, sidecar_path in entries:
        videos.append(
            {
                "video_id": name,
                "camera_id": CAMERA_ID,
                "video": os.path.relpath(video_path, manifest_dir).replace("\\", "/"),
                "sidecar": os.path.relpath(sidecar_path, manifest_dir).replace("\\", "/"),
            }
        )
    manifest = {"policies_dir": "configs/policies", "videos": videos}
    import yaml

    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic warehouse videos")
    parser.add_argument("--out", default="datasets/videos", help="output directory for videos")
    parser.add_argument("--manifest", default="datasets/manifests/eval.yaml")
    args = parser.parse_args()

    out_dir = Path(args.out)
    entries: list[tuple[str, Path, Path]] = []
    for factory in SCENARIOS:
        scenario = factory()
        video_path, sidecar_path = render_scenario(scenario, out_dir)
        entries.append((scenario.name, video_path, sidecar_path))
        print(f"generated {video_path.name} ({scenario.duration_s}s) + ground truth")

    write_manifest(entries, Path(args.manifest))
    print(f"wrote manifest {args.manifest}")


if __name__ == "__main__":
    main()
