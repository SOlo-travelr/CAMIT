"""Initialize the database schema."""

from __future__ import annotations

import argparse

from sentinel.config import load_config
from sentinel.storage.database import Database


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the Sentinel database")
    parser.add_argument("--config", default="configs/development.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    db = Database(config.resolved_database_url())
    db.create_all()
    print(f"Database initialized at {config.resolved_database_url()}")


if __name__ == "__main__":
    main()
