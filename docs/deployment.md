# Deployment

## Local (no Docker, no GPU)

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts/generate_test_videos.py --out datasets/videos
python scripts/run_benchmark.py --dataset datasets/manifests/eval.yaml --config configs/development.yaml
pytest -q
uvicorn apps.api.main:app --reload
python -m apps.worker.main            # replays a demo clip, persists an incident
```

Without a `DATABASE_URL`, the platform uses a local SQLite database and a
local-filesystem object store, so everything runs on a laptop.

## Docker Compose (Postgres + Redis + MinIO + Prometheus)

```bash
cp .env.example .env
docker compose up -d
curl http://localhost:8000/health
```

## Model detector

The default `synthetic` detector replays ground-truth for reproducible tests.
For real footage install the perception extra and switch the config backend:

```bash
pip install -e ".[perception]"      # Ultralytics YOLO + ByteTrack
```

```yaml
detector: { backend: ultralytics, model: yolov8m.pt }
tracker:  { backend: bytetrack }
```

## Scaling later

Introduce NVIDIA DeepStream only after the Python pipeline is correct and stream
density demands GPU-accelerated GStreamer/TensorRT. Do not start there.
Kafka/Kubernetes/vector-DBs are intentionally deferred.
