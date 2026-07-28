# Sentinel Platform

Edge-capable video-intelligence platform for **industrial safety**. It connects to
recorded videos, webcams and RTSP cameras, detects and tracks people and vehicles,
and raises evidence-backed incidents for four events:

1. Restricted-zone entry
2. Loitering
3. Pedestrian–vehicle proximity
4. Predicted pedestrian–vehicle collision risk

## Design principle

The real-time path is deterministic:

```
decode → detect → track → update state → evaluate rules → emit event
```

An LLM (optional) only translates natural-language policies into validated JSON and
explains incidents. It never sits inside the frame loop, assigns track IDs, or
computes distances.

## Quick start (no GPU, no Docker required)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Generate deterministic synthetic warehouse videos with ground-truth
python scripts/generate_test_videos.py --out datasets/videos

# Run the full offline benchmark on the generated data
python scripts/run_benchmark.py --dataset datasets/manifests/eval.yaml --config configs/development.yaml

# Run the test suite (core logic needs no ML deps)
pytest -q
```

## API

```powershell
uvicorn apps.api.main:app --reload
curl http://localhost:8000/health
```

## Optional components

- Model detector: `pip install -e ".[perception]"` (Ultralytics YOLO adapter).
- Infra clients (Redis/MinIO/Prometheus/Postgres): `pip install -e ".[infra]"`.
- Experiment tracking: `pip install -e ".[tracking]"` (MLflow).

The platform runs fully with the built-in synthetic detector + built-in tracker so
you can validate event logic end-to-end without any model download.

## Repository layout

See [docs/architecture.md](docs/architecture.md).

## Development phases

The build follows the phased plan in [docs/architecture.md](docs/architecture.md#phases):
Phase 0 foundation → 1 perception → 2 events → 3 incidents → 4 calibration/risk →
5 evaluation → 6 policy translator → 7 live RTSP.
