"""Worker entrypoint. Replays generated demo videos through the full pipeline,
persisting incidents with evidence. In production this would consume the camera
inventory and run one pipeline per camera.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from apps.api.dependencies import get_database, get_object_store
from apps.worker.camera_worker import build_pipeline_from_sidecar
from sentinel.config import load_config
from sentinel.observability.logging import configure_logging, get_logger

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sentinel camera worker")
    parser.add_argument("--config", default="configs/development.yaml")
    parser.add_argument("--video", default="datasets/videos/near_miss.mp4")
    parser.add_argument("--sidecar", default="datasets/videos/near_miss.gt.json")
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level, config.logging.json_output)

    database = get_database()
    store = get_object_store()

    if not Path(args.sidecar).exists():
        logger.error("sidecar not found; run scripts/generate_test_videos.py first")
        return

    pipeline = build_pipeline_from_sidecar(
        args.sidecar, args.video, config, database=database, object_store=store
    )
    result = pipeline.run()
    logger.info(
        "worker finished",
        extra={"extra_fields": {"frames": result.frames, "incidents": len(result.incidents)}},
    )
    for inc in result.incidents:
        print(f"  incident {inc.incident_id} {inc.event_type} clip={inc.evidence.clip_uri}")


if __name__ == "__main__":
    main()
