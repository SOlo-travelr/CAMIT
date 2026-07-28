"""Run the offline benchmark over a manifest and write metrics + report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentinel.config import load_config
from sentinel.evaluation.benchmark import run_benchmark
from sentinel.observability.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Sentinel offline benchmark")
    parser.add_argument("--dataset", required=True, help="path to manifest YAML")
    parser.add_argument("--config", required=True, help="path to config YAML")
    parser.add_argument("--output", default="data/benchmark", help="output directory")
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level, config.logging.json_output)

    metrics = run_benchmark(args.dataset, config, args.output)
    ev = metrics["events"]
    print(json.dumps(ev, indent=2))
    print(f"\nReport: {Path(args.output) / 'report.html'}")
    print(f"Metrics: {Path(args.output) / 'metrics.json'}")


if __name__ == "__main__":
    main()
