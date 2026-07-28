# Datasets

The platform is validated on **procedurally generated** warehouse videos whose
ground truth is known exactly. Generate them with:

```powershell
python scripts/generate_test_videos.py --out datasets/videos
```

This writes `videos/*.mp4`, per-video `*.gt.json` sidecars, and the manifest
`manifests/eval.yaml`.

## Manifest format

```yaml
policies_dir: configs/policies
videos:
  - video_id: near_miss
    camera_id: warehouse_cam_03
    video: ../videos/near_miss.mp4
    sidecar: ../videos/near_miss.gt.json
```

## Sidecar (ground truth) format

```json
{
  "camera_id": "warehouse_cam_03",
  "fps": 15, "width": 1280, "height": 720,
  "zones": {"forklift_lane": [[500,300],[900,300],[900,720],[500,720]]},
  "calibration": {"image_points": [...], "world_points_m": [...]},
  "frames": {"0": [{"class_name": "person", "box": [x1,y1,x2,y2], "confidence": 0.95, "gt_id": 1}]},
  "events": [{"event_type": "collision_risk", "start_s": 2.0, "end_s": 4.5, "track_ids": [1,2]}]
}
```

## Scenarios shipped

| Scenario | Events (ground truth) | Purpose |
| --- | --- | --- |
| `restricted_entry` | restricted_zone, loitering | positive zone events |
| `near_miss` | collision_risk | positive metric-risk event |
| `parallel_negative` | (none) | hard negative — parallel courses must not fire |

## Recommended real-data slices (for a site pilot)

Per event: positive; visually similar negative; low light; motion blur; partial
occlusion; crowding; camera vibration; near-boundary; brief entry; stationary
vehicle; vehicle moving away; crossing at different times; tracking interruption;
partially out-of-frame.

Hard negatives for collision risk: parked forklift beside worker; forklift
moving away; person/forklift crossing the same point at different times; worker
behind a barrier; reflection; poster/screen image of a forklift; loading beside a
vehicle; perspective compressing apparent separation.

Annotate real footage in **CVAT**; inspect model failures in **FiftyOne**.
The `import_video.py` helper can fetch an external clip for eyeballing, but such
clips have no ground truth and are not part of the reproducible benchmark.
