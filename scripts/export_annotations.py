"""Export incident tracks/observations to a COCO-like annotation JSON for review
in CVAT or FiftyOne. Placeholder writer wired for later dataset-curation work."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentinel.config import load_config
from sentinel.storage.database import Database
from sentinel.storage.repositories import IncidentRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Export incidents as annotations")
    parser.add_argument("--config", default="configs/development.yaml")
    parser.add_argument("--out", default="datasets/annotations/incidents.json")
    args = parser.parse_args()

    config = load_config(args.config)
    db = Database(config.resolved_database_url())
    db.create_all()
    with db.session() as session:
        incidents = IncidentRepository(session).list(limit=10_000)
        payload = [
            {
                "incident_id": i.id,
                "event_type": i.event_type,
                "camera_id": i.camera_id,
                "start_time": i.start_time.isoformat(),
                "end_time": i.end_time.isoformat(),
                "track_ids": i.track_ids,
                "review_status": i.review_status,
            }
            for i in incidents
        ]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Exported {len(payload)} incidents to {out}")


if __name__ == "__main__":
    main()
